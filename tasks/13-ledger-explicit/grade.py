#!/usr/bin/env python3
"""Grader for 13-ledger-explicit (explicit arm).

Same numeric items and tolerances as 13-ledger; here the numbers ARE the task,
so the exit status gates on schema AND every item being correct."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, ledger_truth, parse_number, parse_signed_pct,
                      money_ok, pct_ok, classify_money, classify_pct)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = ledger_truth(os.path.join(HERE, "fixture"))
CATS = T["categories"]
B = T["bases"]

path = os.path.join(WS, "RESULTS.json")
data = None
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = None
r.gate("file", isinstance(data, dict), "RESULTS.json parses to an object")
data = data if isinstance(data, dict) else {}

REQUIRED = ["category_totals_eur", "q2_total_eur", "mom_may_pct", "mom_jun_pct",
            "largest_txn_eur", "mean_txn_eur", "travel_share_pct", "over_budget"]
r.gate("schema", all(k in data for k in REQUIRED))

cat_map = data.get("category_totals_eur") or {}
for c in CATS:
    canon = [B["per_txn"]["cat"][c], B["end"]["cat"][c]]
    got = parse_number(cat_map.get(c))
    r.item(f"cat_{c}", str(B["per_txn"]["cat"][c]), got,
           money_ok(got, canon), classify_money(got, canon, T["raw_cat"][c]))

got = parse_number(data.get("q2_total_eur"))
canon = [B["per_txn"]["q2"], B["end"]["q2"]]
r.item("q2_total", str(B["per_txn"]["q2"]), got,
       money_ok(got, canon), classify_money(got, canon, T["raw_all"]))

months = sorted(B["per_txn"]["mom"])
for item, key, mon in (("mom_may", "mom_may_pct", months[0]),
                       ("mom_jun", "mom_jun_pct", months[1])):
    got = parse_signed_pct(data.get(key))
    canon = [B["per_txn"]["mom"][mon], B["end"]["mom"][mon]]
    r.item(item, f"{canon[0]:.1f}", got, pct_ok(got, canon),
           classify_pct(got, canon))

got = parse_number(data.get("largest_txn_eur"))
canon = [B["per_txn"]["largest"], B["end"]["largest"]]
r.item("largest_txn", str(B["per_txn"]["largest"]), got,
       money_ok(got, canon), classify_money(got, canon))

got = parse_number(data.get("mean_txn_eur"))
canon = [B["per_txn"]["mean"], B["end"]["mean"]]
r.item("mean_txn", f"{canon[0]:.2f}", got, money_ok(got, canon, tol="0.03"),
       classify_money(got, canon))

got = parse_signed_pct(data.get("travel_share_pct"))
canon = [B["per_txn"]["travel_share"], B["end"]["travel_share"]]
r.item("travel_share", f"{canon[0]:.1f}", got, pct_ok(got, canon),
       classify_pct(got, canon))

ob = data.get("over_budget")
got_over = sorted(str(x).strip().lower() for x in ob) if isinstance(ob, list) else None
r.item("over_budget_set", ",".join(T["over_budget"]),
       ",".join(got_over) if got_over is not None else None,
       got_over == sorted(T["over_budget"]))

sys.exit(r.finish(gate_exit=False))
