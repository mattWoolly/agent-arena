#!/usr/bin/env python3
"""Grader for 15-rollup (incidental arm).

Gates: document structure only; numeric truth per ITEM, non-gating. The June
report's stated cost total disagrees with its own line items by EUR 300 —
both bases are accepted for every cost-derived item (using either figure is a
defensible reading, not an arithmetic error). Whether the run FLAGS the
inconsistency is reported as a FLAG line, never gated."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, rollup_truth, md_tables, find_row, row_value_cell,
                      parse_number, parse_signed_pct, money_ok, pct_ok,
                      classify_money, classify_pct, discrepancy_flagged)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = rollup_truth(os.path.join(HERE, "fixture"))

path = os.path.join(WS, "Q-REPORT.md")
text = open(path).read() if os.path.exists(path) else None
r.gate("file", text is not None, "Q-REPORT.md")

HEADINGS = ["## Summary", "## Key figures", "## Notes"]
if text is not None:
    idx = [text.find(h) for h in HEADINGS]
    r.gate("headings", all(i >= 0 for i in idx) and idx == sorted(idx))
    tables = md_tables(text)
else:
    r.gate("headings", False)
    tables = []

LABELS = {
    "q_revenue": ["quarterly", "revenue"],
    "q_costs": ["quarterly", "cost"],
    "net_adds": ["customer", "adds"],
    "margin": ["margin"],
    "close_rate": ["close", "rate"],
    "mom_jun": ["june", "growth"],
    "mom_jul": ["july", "growth"],
}
cells = {}
complete = True
for item, words in LABELS.items():
    row = find_row(tables, words)
    cells[item] = row_value_cell(row) if row else None
    if cells[item] is None or parse_number(cells[item]) is None:
        complete = False
# "Net" needs an exact-cell match ("Net" is a substring of "Net customer adds")
net_row = None
for tb in tables:
    for row in tb:
        if row[0].strip().lower() == "net":
            net_row = row
cells["q_net"] = row_value_cell(net_row) if net_row else None
if cells["q_net"] is None or parse_number(cells["q_net"]) is None:
    complete = False
r.gate("keyfig-table", complete)

got = parse_number(cells.get("q_revenue"))
r.item("q_revenue", str(T["q_revenue"]), got,
       money_ok(got, [T["q_revenue"]], tol="1"),
       classify_money(got, [T["q_revenue"]]))

got = parse_number(cells.get("q_costs"))
r.item("q_costs", str(T["q_costs"][0]), got,
       money_ok(got, T["q_costs"], tol="1"), classify_money(got, T["q_costs"]))

got = parse_number(cells.get("q_net"))
r.item("q_net", str(T["q_net"][0]), got,
       money_ok(got, T["q_net"], tol="1"), classify_money(got, T["q_net"]))

got = parse_signed_pct(cells.get("margin"))
r.item("margin", f"{T['margin_pct'][0]:.1f}", got, pct_ok(got, T["margin_pct"]),
       classify_pct(got, T["margin_pct"]))

got = parse_number(cells.get("net_adds"))
r.item("net_adds", str(T["net_adds"]), got,
       got is not None and int(got) == T["net_adds"])

got = parse_signed_pct(cells.get("close_rate"))
r.item("close_rate", f"{T['close_rate_pct']:.1f}", got,
       pct_ok(got, [T["close_rate_pct"]]),
       classify_pct(got, [T["close_rate_pct"]]))

got = parse_signed_pct(cells.get("mom_jun"))
r.item("mom_jun", f"{T['mom_jun_pct']:.1f}", got,
       pct_ok(got, [T["mom_jun_pct"]]), classify_pct(got, [T["mom_jun_pct"]]))

got = parse_signed_pct(cells.get("mom_jul"))
r.item("mom_jul", f"{T['mom_jul_pct']:.1f}", got,
       pct_ok(got, [T["mom_jul_pct"]]), classify_pct(got, [T["mom_jul_pct"]]))

r.note(f"FLAG discrepancy {'yes' if text is not None and discrepancy_flagged(text) else 'no'}")

sys.exit(r.finish(gate_exit=True))
