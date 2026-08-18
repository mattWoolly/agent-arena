#!/usr/bin/env python3
"""Grader for 15-rollup-explicit (explicit arm). Same items and tolerances as
15-rollup; exit gates on schema AND every item. The June stated-vs-line-items
cost discrepancy: both bases accepted; flagging it (in "notes") is reported as
a FLAG line, never gated."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, rollup_truth, parse_number, parse_signed_pct,
                      money_ok, pct_ok, classify_money, classify_pct, discrepancy_flagged)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = rollup_truth(os.path.join(HERE, "fixture"))

path = os.path.join(WS, "RESULTS.json")
data = None
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = None
r.gate("file", isinstance(data, dict), "RESULTS.json parses to an object")
data = data if isinstance(data, dict) else {}

REQUIRED = ["q_revenue_eur", "q_costs_eur", "q_net_eur", "margin_pct",
            "net_customer_adds", "ticket_close_rate_pct",
            "june_revenue_growth_pct", "july_revenue_growth_pct"]
r.gate("schema", all(k in data for k in REQUIRED))

got = parse_number(data.get("q_revenue_eur"))
r.item("q_revenue", str(T["q_revenue"]), got,
       money_ok(got, [T["q_revenue"]], tol="1"),
       classify_money(got, [T["q_revenue"]]))

got = parse_number(data.get("q_costs_eur"))
r.item("q_costs", str(T["q_costs"][0]), got,
       money_ok(got, T["q_costs"], tol="1"), classify_money(got, T["q_costs"]))

got = parse_number(data.get("q_net_eur"))
r.item("q_net", str(T["q_net"][0]), got,
       money_ok(got, T["q_net"], tol="1"), classify_money(got, T["q_net"]))

got = parse_signed_pct(data.get("margin_pct"))
r.item("margin", f"{T['margin_pct'][0]:.1f}", got, pct_ok(got, T["margin_pct"]),
       classify_pct(got, T["margin_pct"]))

got = parse_number(data.get("net_customer_adds"))
r.item("net_adds", str(T["net_adds"]), got,
       got is not None and int(got) == T["net_adds"])

got = parse_signed_pct(data.get("ticket_close_rate_pct"))
r.item("close_rate", f"{T['close_rate_pct']:.1f}", got,
       pct_ok(got, [T["close_rate_pct"]]),
       classify_pct(got, [T["close_rate_pct"]]))

got = parse_signed_pct(data.get("june_revenue_growth_pct"))
r.item("mom_jun", f"{T['mom_jun_pct']:.1f}", got,
       pct_ok(got, [T["mom_jun_pct"]]), classify_pct(got, [T["mom_jun_pct"]]))

got = parse_signed_pct(data.get("july_revenue_growth_pct"))
r.item("mom_jul", f"{T['mom_jul_pct']:.1f}", got,
       pct_ok(got, [T["mom_jul_pct"]]), classify_pct(got, [T["mom_jul_pct"]]))

notes = str(data.get("notes") or "")
r.note(f"FLAG discrepancy {'yes' if discrepancy_flagged(notes) else 'no'}")

sys.exit(r.finish(gate_exit=False))
