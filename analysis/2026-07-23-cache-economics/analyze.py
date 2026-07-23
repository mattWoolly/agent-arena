#!/usr/bin/env python3
"""Cache economics reanalysis (2026-07-23), per DESIGN.md in this directory.

Zero API calls: reads committed bout artifacts only. Produces economics.json
and prints the hypothesis verdicts.

Accounting notes (normalizations promised in DESIGN.md):
- Anthropic-format usage (all Claude arms, kimi-k3, glm-5.2): input_tokens
  EXCLUDES cache reads and writes; the four classes are disjoint.
- OpenAI-format usage (gpt-5.6-sol via proxy sidecar): prompt_tokens
  INCLUDES cached_tokens; uncached input = prompt_tokens - cached_tokens.
  OpenAI does not report cache-write tokens, so Sol's write premium (1.25x)
  is not separable; written tokens are billed here at the plain input rate,
  which understates Sol's input-side dollars by at most 25% of the written
  span. Disclosed in the note.
- Per-request records are deduped by API message id (a multi-block message
  appears on several transcript lines with the same usage).
- glm-5.2 zeroes per-request usage through its endpoint; its runs use the
  result.json aggregate (same four classes), matching committed metrics.py
  behavior. Long-context surcharges (Sol only) cannot be judged from an
  aggregate; all GLM/Kimi/Claude prompts stayed far below any threshold.
- DEVIATION from DESIGN's per-request wording: all Anthropic-format arms
  use the CLI's reconciled per-run aggregate (result.json usage), because
  transcript usage records under-report output tokens (usage logs at
  message start; the final output count lands only in the aggregate), and
  kimi-k3's endpoint additionally lumps the whole prompt into
  input_tokens per request with zeroed cache fields. The aggregate equals
  the main model's modelUsage entry exactly. Same four token classes.
  Sub-cent haiku helper-model usage inside runs is excluded (per-model
  decomposition covers the arm's main model only).
- Observation: the CLI's own costUSD for Sonnet 5 in the 07-07 bout
  reproduces exactly at LIST prices (3/15), not intro pricing; published
  ladder CLI costs therefore reflect list, while actual invoices during
  the intro window were lower.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

# List prices, USD per MTok. Anthropic cache: write 1.25x input (5m TTL,
# verified against transcripts), read 0.10x input. Non-Anthropic prices
# mirror env/prices.json as committed with each bout.
PRICES = {
    "claude-haiku-4-5":  {"in": 1.0,  "out": 5.0,  "read": 0.10, "wmult": 1.25},
    "claude-sonnet-5":   {"in": 3.0,  "out": 15.0, "read": 0.30, "wmult": 1.25},
    "claude-opus-4-8":   {"in": 5.0,  "out": 25.0, "read": 0.50, "wmult": 1.25},
    "claude-fable-5":    {"in": 10.0, "out": 50.0, "read": 1.00, "wmult": 1.25},
    "kimi-k3":           {"in": 3.0,  "out": 15.0, "read": 0.30, "wmult": 1.0},
    "glm-5.2":           {"in": 1.4,  "out": 4.4,  "read": 0.26, "wmult": 1.0},
    "gpt-5.6-sol":       {"in": 5.0,  "out": 30.0, "read": 0.50, "wmult": 1.0,
                          "long_threshold": 272000, "long_in": 2.0, "long_out": 1.5},
}
SONNET5_INTRO = {"in": 2.0, "out": 10.0, "read": 0.20, "wmult": 1.25}

ARMS = [
    ("ladder", "bouts/2026-07-07-ladder-noise", "claude-haiku-4-5"),
    ("ladder", "bouts/2026-07-07-ladder-noise", "claude-sonnet-5"),
    ("ladder", "bouts/2026-07-07-ladder-noise", "claude-opus-4-8"),
    ("ladder", "bouts/2026-07-07-ladder-noise", "claude-fable-5"),
    ("3way", "bouts/2026-07-17-fable-sol-kimi", "claude-fable-5"),
    ("3way", "bouts/2026-07-17-fable-sol-kimi", "gpt-5.6-sol"),
    ("3way", "bouts/2026-07-17-fable-sol-kimi", "kimi-k3"),
    ("glm52", "bouts/2026-07-20-glm52", "glm-5.2"),
    ("glm52", "bouts/2026-07-20-glm52", "claude-opus-4-8"),
]


def run_dirs(bout: Path, model: str):
    for task_dir in sorted(bout.iterdir()):
        mdir = task_dir / model
        if not mdir.is_dir():
            continue
        subs = sorted(d for d in mdir.iterdir()
                      if d.is_dir() and d.name.startswith("run-"))
        yield from (subs or [mdir])


def aggregate_ledger(rdir: Path):
    agg = json.loads((rdir / "result.json").read_text()).get("usage") or {}
    return [{"in": agg.get("input_tokens") or 0,
             "write": agg.get("cache_creation_input_tokens") or 0,
             "read": agg.get("cache_read_input_tokens") or 0,
             "out": agg.get("output_tokens") or 0}]


def sol_ledger(rdir: Path):
    """Per-request token classes from the proxy sidecar's raw OpenAI usage."""
    reqs = []
    for line in (rdir / "proxy_usage.jsonl").read_text().splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw = rec.get("raw_usage") or {}
        prompt = raw.get("prompt_tokens") or 0
        cached = (raw.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        comp = raw.get("completion_tokens") or 0
        if prompt + comp == 0:
            continue
        reqs.append({"in": prompt - cached, "write": 0, "read": cached,
                     "out": comp, "prompt_total": prompt})
    return reqs


def price_request(r: dict, p: dict) -> dict:
    in_mult = out_mult = 1.0
    thr = p.get("long_threshold")
    if thr and r.get("prompt_total", r["in"] + r["read"] + r["write"]) > thr:
        in_mult, out_mult = p["long_in"], p["long_out"]
    return {
        "usd_in": r["in"] * p["in"] * in_mult / 1e6,
        "usd_write": r["write"] * p["in"] * p["wmult"] / 1e6,
        "usd_read": r["read"] * p["read"] / 1e6,
        "usd_out": r["out"] * p["out"] * out_mult / 1e6,
    }


def main():
    arms = []
    for bout_label, bout_rel, model in ARMS:
        bout = ROOT / bout_rel
        p = PRICES[model]
        tot = {"in": 0, "write": 0, "read": 0, "out": 0}
        usd = {"usd_in": 0.0, "usd_write": 0.0, "usd_read": 0.0, "usd_out": 0.0}
        runs = 0
        cli_costs, out_tok_per_run, out_usd_per_run = [], [], []
        for rdir in run_dirs(bout, model):
            # All Anthropic-format arms use the CLI's reconciled per-run
            # aggregate: transcripts under-report output tokens (usage is
            # logged at message start; final output counts appear only in
            # the aggregate). Verified: the aggregate equals the main
            # model's modelUsage entry exactly. Sol keeps the per-request
            # sidecar records (authoritative raw OpenAI usage; also needed
            # for the per-request long-context surcharge).
            reqs = (sol_ledger(rdir) if model == "gpt-5.6-sol"
                    else aggregate_ledger(rdir))
            if not reqs:
                continue
            runs += 1
            run_out_tok = run_out_usd = 0
            for r in reqs:
                for k in tot:
                    tot[k] += r[k]
                d = price_request(r, p)
                for k in usd:
                    usd[k] += d[k]
                run_out_tok += r["out"]
                run_out_usd += d["usd_out"]
            out_tok_per_run.append(run_out_tok)
            out_usd_per_run.append(run_out_usd)
            m = json.loads((rdir / "metrics.json").read_text())
            if m.get("total_cost_usd_cli") is not None and m.get("total_cost_usd"):
                cli_costs.append((m["total_cost_usd_cli"], m["total_cost_usd"]))
        tok_total = sum(tot.values())
        usd_total = sum(usd.values())
        input_side_tok = tot["in"] + tot["write"] + tot["read"]
        input_side_usd = usd["usd_in"] + usd["usd_write"] + usd["usd_read"]
        arm = {
            "bout": bout_label, "model": model, "runs": runs,
            "tokens": tot, "usd": {k: round(v, 4) for k, v in usd.items()},
            "usd_total": round(usd_total, 4),
            "read_share_tokens": round(tot["read"] / tok_total, 4),
            "read_share_usd": round(usd["usd_read"] / usd_total, 4),
            "out_share_tokens": round(tot["out"] / tok_total, 4),
            "out_share_usd": round(usd["usd_out"] / usd_total, 4),
            "effective_input_rate_per_mtok":
                round(input_side_usd / input_side_tok * 1e6, 4),
            "effective_input_rate_vs_sticker":
                round((input_side_usd / input_side_tok * 1e6) / p["in"], 4),
            "mean_out_tokens_per_run": round(sum(out_tok_per_run) / runs, 1),
            "mean_out_usd_per_run": round(sum(out_usd_per_run) / runs, 5),
            "usd_per_run": round(usd_total / runs, 4),
        }
        if cli_costs:
            over = [(c - t) / t for c, t in cli_costs]
            arm["cli_vs_recomputed_mean_overstatement"] = round(
                sum(over) / len(over), 4)
            arm["cli_pairs"] = len(cli_costs)
        arms.append(arm)
        print(f"{bout_label}/{model}: {runs} runs, ${arm['usd_per_run']}/run, "
              f"read {arm['read_share_tokens']:.1%} tok / "
              f"{arm['read_share_usd']:.1%} usd, "
              f"out {arm['out_share_tokens']:.1%} tok / "
              f"{arm['out_share_usd']:.1%} usd, "
              f"eff-in {arm['effective_input_rate_vs_sticker']:.1%} of sticker",
              flush=True)

    # Sonnet 5 intro-pricing sidebar (ladder arm only)
    # ---- hypothesis verdicts ----
    by = {(a["bout"], a["model"]): a for a in arms}
    h = {}
    h["H1"] = {"read_tok_gt_85_all": all(a["read_share_tokens"] > 0.85 for a in arms),
               "read_usd_lt_50_any": any(a["read_share_usd"] < 0.50 for a in arms)}
    h["H1"]["pass"] = h["H1"]["read_tok_gt_85_all"] and h["H1"]["read_usd_lt_50_any"]
    h["H2"] = {"out_tok_lt_5_all": all(a["out_share_tokens"] < 0.05 for a in arms),
               "arms_out_usd_gt_30": sum(a["out_share_usd"] > 0.30 for a in arms)}
    h["H2"]["pass"] = h["H2"]["out_tok_lt_5_all"] and h["H2"]["arms_out_usd_gt_30"] >= 2
    h["H3"] = {"in_band_all": all(0.12 <= a["effective_input_rate_vs_sticker"] <= 0.25
                                  for a in arms),
               "rates": {f"{a['bout']}/{a['model']}":
                         a["effective_input_rate_vs_sticker"] for a in arms}}
    h["H3"]["pass"] = h["H3"]["in_band_all"]
    kimi, sol = by[("3way", "kimi-k3")], by[("3way", "gpt-5.6-sol")]
    h["H4"] = {"kimi_out_usd": kimi["mean_out_usd_per_run"],
               "sol_out_usd": sol["mean_out_usd_per_run"],
               "kimi_out_tok": kimi["mean_out_tokens_per_run"],
               "sol_out_tok": sol["mean_out_tokens_per_run"]}
    h["H4"]["pass"] = (kimi["mean_out_usd_per_run"] < sol["mean_out_usd_per_run"]
                       and kimi["mean_out_tokens_per_run"] > sol["mean_out_tokens_per_run"])
    h["H5"] = {"mean_overstatement": sol.get("cli_vs_recomputed_mean_overstatement"),
               "pairs": sol.get("cli_pairs")}
    h["H5"]["pass"] = (h["H5"]["mean_overstatement"] or 0) > 0.25

    out = {"arms": arms, "hypotheses": h,
           "prices_used": PRICES, "sonnet5_intro_note": SONNET5_INTRO}
    (OUT / "economics.json").write_text(json.dumps(out, indent=1))
    print()
    for k in sorted(h):
        print(k, "PASS" if h[k]["pass"] else "MISS", h[k], flush=True)


if __name__ == "__main__":
    main()
