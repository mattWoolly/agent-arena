#!/usr/bin/env python3
"""Deterministic fixture generator for the incidental-arithmetic bout.

Writes the data files for tasks 13-ledger, 14-schedule, 15-rollup (and their
-explicit twins, byte-identical fixtures). Prints the ground truth it implies,
for author-side sanity checks only — graders recompute everything from the
fixtures independently; nothing printed here is consumed by any grader.

Run from the repo root:  python3 bouts/2026-08-17-incidental-arithmetic/gen_fixtures.py
"""
import csv
import io
import json
import os
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TASKS = os.path.join(ROOT, "tasks")

rng = random.Random(20260817)


def write_both(task, relpath, content):
    for t in (task, task + "-explicit"):
        p = os.path.join(TASKS, t, "fixture", relpath)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(content)


def cents(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- 13-ledger
CATEGORIES = ["travel", "software", "hardware", "meals", "training", "office"]
RATES = {"EUR": Decimal("1.00"), "USD": Decimal("0.92"), "GBP": Decimal("1.17")}
DESCRIPTIONS = {
    "travel": ["flight", "hotel", "rail ticket", "taxi", "car rental"],
    "software": ["SaaS subscription", "license renewal", "API credits", "plugin"],
    "hardware": ["monitor", "dock", "SSD", "keyboard", "cables"],
    "meals": ["team lunch", "client dinner", "catering", "coffee"],
    "training": ["course", "conference ticket", "workshop", "books"],
    "office": ["stationery", "cleaning", "plants", "snacks", "printer paper"],
}
# (min, max) amount per category, in the transaction's own currency
RANGES = {
    "travel": (45, 1450),
    "software": (19, 890),
    "hardware": (25, 1150),
    "meals": (12, 240),
    "training": (60, 990),
    "office": (8, 180),
}

def gen_ledger():
    start = date(2026, 4, 1)
    rows = []
    for i in range(120):
        d = start + timedelta(days=rng.randrange(0, 91))
        cat = rng.choice(CATEGORIES)
        cur = rng.choices(["EUR", "USD", "GBP"], weights=[6, 3, 2])[0]
        lo, hi = RANGES[cat]
        amt = cents(Decimal(rng.uniform(lo, hi)))
        rows.append((d, cat, rng.choice(DESCRIPTIONS[cat]), amt, cur))
    rows.sort(key=lambda r: (r[0], r[1]))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "date", "category", "description", "amount", "currency"])
    for i, (d, cat, desc, amt, cur) in enumerate(rows, 1):
        w.writerow([f"T{i:04d}", d.isoformat(), cat, desc, f"{amt}", cur])
    write_both("13-ledger", "transactions.csv", buf.getvalue())

    write_both("13-ledger", "rates.csv",
               "currency,eur_per_unit\nEUR,1.00\nUSD,0.92\nGBP,1.17\n")

    # Ground truth (author-side check only)
    def eur(amt, cur):
        return cents(amt * RATES[cur])

    cat_tot = {c: Decimal("0") for c in CATEGORIES}
    mon_tot = {4: Decimal("0"), 5: Decimal("0"), 6: Decimal("0")}
    conv = []
    for (d, cat, desc, amt, cur) in rows:
        e = eur(amt, cur)
        cat_tot[cat] += e
        mon_tot[d.month] += e
        conv.append(e)
    q2 = sum(conv)
    truth = {
        "cat_total": {c: str(cat_tot[c]) for c in CATEGORIES},
        "q2_total": str(q2),
        "month_total": {m: str(mon_tot[m]) for m in mon_tot},
        "mom_may_pct": str(((mon_tot[5] - mon_tot[4]) / mon_tot[4] * 100).quantize(Decimal("0.1"))),
        "mom_jun_pct": str(((mon_tot[6] - mon_tot[5]) / mon_tot[5] * 100).quantize(Decimal("0.1"))),
        "largest_txn_eur": str(max(conv)),
        "mean_txn_eur": str(cents(q2 / 120)),
        "travel_share_pct": str((cat_tot["travel"] / q2 * 100).quantize(Decimal("0.1"))),
    }

    # Budgets chosen relative to actuals: travel and software over budget by a
    # clear margin, the rest under by a clear margin (>=8% away from the line
    # in every case, so flag correctness never rides on rounding).
    budgets = {}
    for c in CATEGORIES:
        t = cat_tot[c]
        if c in ("travel", "software"):
            budgets[c] = int((t * Decimal("0.85")) / 100) * 100  # over budget
        else:
            budgets[c] = int((t * Decimal("1.20")) / 100) * 100 + 100  # under
    y = ["# Quarterly budget, Q2 2026, EUR", "budgets:"]
    for c in CATEGORIES:
        y.append(f"  {c}: {budgets[c]}")
    write_both("13-ledger", "budget.yaml", "\n".join(y) + "\n")
    truth["budgets"] = budgets
    truth["over_budget"] = [c for c in CATEGORIES if cat_tot[c] > budgets[c]]
    return truth


# -------------------------------------------------------------- 14-schedule
MILESTONES = [
    ("kickoff", 3),
    ("requirements", 7),
    ("architecture", 5),
    ("build-core", 12),
    ("build-integrations", 9),
    ("hardening", 6),
    ("acceptance", 4),
    ("launch", 2),
]
HOLIDAYS = [date(2026, 8, 31), date(2026, 9, 25), date(2026, 10, 12)]
TODAY = date(2026, 8, 17)
KICKOFF_START = date(2026, 8, 24)

def is_bday(d):
    return d.weekday() < 5 and d not in HOLIDAYS

def next_bday(d):
    d = d + timedelta(days=1)
    while not is_bday(d):
        d = d + timedelta(days=1)
    return d

def add_bdays_inclusive(start, n):
    """End date of a span of n business days that includes start."""
    d = start
    count = 1
    while count < n:
        d = next_bday(d)
        count += 1
    return d

def gen_schedule():
    y = ["# Delivery plan input — see PROMPT for the scheduling conventions",
         f"project_start: {KICKOFF_START.isoformat()}",
         "milestones:"]
    for name, dur in MILESTONES:
        y.append(f"  - name: {name}")
        y.append(f"    duration_business_days: {dur}")
    write_both("14-schedule", "milestones.yaml", "\n".join(y) + "\n")
    write_both("14-schedule", "holidays.csv",
               "date,name\n" + "".join(f"{d.isoformat()},company holiday {i+1}\n"
                                       for i, d in enumerate(HOLIDAYS)))

    truth = {"milestones": {}}
    start = KICKOFF_START
    for i, (name, dur) in enumerate(MILESTONES):
        if i > 0:
            start = next_bday(prev_end)
        end = add_bdays_inclusive(start, dur)
        truth["milestones"][name] = {"start": start.isoformat(), "end": end.isoformat()}
        prev_end = end
    launch_end = prev_end
    # total business days kickoff start -> launch end, inclusive
    d, n = KICKOFF_START, 0
    while d <= launch_end:
        if is_bday(d):
            n += 1
        d += timedelta(days=1)
    truth["total_business_days"] = n
    # business days from TODAY (exclusive) to kickoff start (inclusive)
    d, n2 = TODAY, 0
    while d < KICKOFF_START:
        d += timedelta(days=1)
        if is_bday(d):
            n2 += 1
    truth["bdays_today_to_kickoff"] = n2
    return truth


# ---------------------------------------------------------------- 15-rollup
ROLLUP = {
    "May": {
        "revenue": 412_380, "cost_lines": [("payroll", 96_400), ("cloud", 21_310),
            ("marketing", 18_650), ("office & travel", 9_240), ("other", 5_520)],
        "new": 86, "churn": 17, "opened": 342, "closed": 315,
    },
    "June": {
        "revenue": 431_205, "cost_lines": [("payroll", 98_100), ("cloud", 23_940),
            ("marketing", 21_400), ("office & travel", 10_180), ("other", 4_920)],
        # stated total is 300 LOW vs the line items (158,540): planted discrepancy
        "stated_costs": 158_240,
        "new": 74, "churn": 22, "opened": 361, "closed": 350,
    },
    "July": {
        "revenue": 389_640, "cost_lines": [("payroll", 98_100), ("cloud", 24_760),
            ("marketing", 16_980), ("office & travel", 12_310), ("other", 6_130)],
        "new": 63, "churn": 31, "opened": 298, "closed": 291,
    },
}

def month_md(name, m):
    lines_total = sum(v for _, v in m["cost_lines"])
    stated = m.get("stated_costs", lines_total)
    rows = "\n".join(f"| {k} | {v:,} |" for k, v in m["cost_lines"])
    return f"""# Monthly operations report — {name} 2026

## Financials

Revenue for {name} came in at **€{m['revenue']:,}**.

| Cost line | EUR |
|---|---|
{rows}

Total costs: **€{stated:,}**.

## Customers

We signed {m['new']} new customers and churned {m['churn']}.

## Support

{m['opened']} tickets opened, {m['closed']} closed.
"""

def gen_rollup():
    for name in ROLLUP:
        write_both("15-rollup", f"reports/2026-{name.lower()[:3]}.md",
                   month_md(name, ROLLUP[name]))
    rev = {k: v["revenue"] for k, v in ROLLUP.items()}
    lines = {k: sum(x for _, x in v["cost_lines"]) for k, v in ROLLUP.items()}
    stated = {k: v.get("stated_costs", lines[k]) for k, v in ROLLUP.items()}
    q_rev = sum(rev.values())
    truth = {
        "q_revenue": q_rev,
        "q_costs_lines_basis": sum(lines.values()),
        "q_costs_stated_basis": sum(stated.values()),
        "q_net_lines": q_rev - sum(lines.values()),
        "q_net_stated": q_rev - sum(stated.values()),
        "margin_pct_lines": round((q_rev - sum(lines.values())) / q_rev * 100, 1),
        "margin_pct_stated": round((q_rev - sum(stated.values())) / q_rev * 100, 1),
        "net_adds": sum(v["new"] - v["churn"] for v in ROLLUP.values()),
        "close_rate_pct": round(sum(v["closed"] for v in ROLLUP.values())
                                / sum(v["opened"] for v in ROLLUP.values()) * 100, 1),
        "mom_jun_pct": round((rev["June"] - rev["May"]) / rev["May"] * 100, 1),
        "mom_jul_pct": round((rev["July"] - rev["June"]) / rev["June"] * 100, 1),
        "june_discrepancy": lines["June"] - stated["June"],
    }
    return truth


if __name__ == "__main__":
    out = {"ledger": gen_ledger(), "schedule": gen_schedule(), "rollup": gen_rollup()}
    print(json.dumps(out, indent=2, default=str))
