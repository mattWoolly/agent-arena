#!/usr/bin/env python3
"""Grader for 13-ledger (incidental arm).

Exit status follows the DOCUMENT gates only (structure, coverage, internal
consistency) — numeric truth is scored per ITEM but does not gate, by design:
that is what makes silent numeric errors observable here the way they are in
the wild. The explicit twin gates on the numbers."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, ledger_truth, md_tables, find_row, row_value_cell,
                      parse_number, parse_signed_pct, money_ok, pct_ok,
                      classify_money, classify_pct)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = ledger_truth(os.path.join(HERE, "fixture"))
CATS = T["categories"]

path = os.path.join(WS, "BRIEFING.md")
text = open(path).read() if os.path.exists(path) else None
r.gate("file", text is not None, "BRIEFING.md")

HEADINGS = ["## Overview", "## Key figures", "## Category breakdown",
            "## Trends and risks"]
if text is not None:
    idx = [text.find(h) for h in HEADINGS]
    r.gate("headings", all(i >= 0 for i in idx) and idx == sorted(idx))
    tables = md_tables(text)
else:
    r.gate("headings", False)
    tables = []


def exact_row(name):
    for tb in tables:
        for row in tb:
            if row[0].strip().lower() == name.lower():
                return row
    return None


# --- Category breakdown table: one row per category, total/budget/status
cat_rows = {c: exact_row(c) for c in CATS}
cat_vals, cat_budget, cat_status = {}, {}, {}
complete = True
for c in CATS:
    row = cat_rows[c]
    if row is None or len(row) < 4:
        complete = False
        cat_vals[c] = None
        continue
    cat_vals[c] = parse_number(row[1])
    cat_budget[c] = parse_number(row[2])
    cat_status[c] = row[3].strip().lower()
    if cat_vals[c] is None or cat_budget[c] is None or \
       not any(w in cat_status[c] for w in ("over", "under")):
        complete = False
r.gate("category-table", complete)

# --- Key figures table
KEYFIG = {
    "q2_total": ["total", "spend"],
    "mean_txn": ["average"],
    "largest_txn": ["largest"],
    "mom_may": ["april"],
    "mom_jun": ["june", "may"],
    "travel_share": ["travel", "share"],
}
keyfig_cells = {}
kf_complete = True
for item, words in KEYFIG.items():
    row = find_row(tables, words)
    cell = row_value_cell(row) if row else None
    keyfig_cells[item] = cell
    if cell is None or parse_number(cell) is None:
        kf_complete = False
r.gate("keyfig-table", kf_complete)

# --- Status column internally consistent with the model's OWN numbers
consistent = True
for c in CATS:
    if cat_vals.get(c) is None or cat_budget.get(c) is None or c not in cat_status:
        consistent = False
        continue
    want = "over" if cat_vals[c] > cat_budget[c] else "under"
    if want not in cat_status[c]:
        consistent = False
r.gate("status-consistent", consistent)

# --- Numeric items (both rounding bases accepted; see numgrade docstring)
B = T["bases"]
for c in CATS:
    canon = [B["per_txn"]["cat"][c], B["end"]["cat"][c]]
    got = cat_vals.get(c)
    r.item(f"cat_{c}", str(B["per_txn"]["cat"][c]), got,
           money_ok(got, canon), classify_money(got, canon, T["raw_cat"][c]))

got = parse_number(keyfig_cells.get("q2_total"))
canon = [B["per_txn"]["q2"], B["end"]["q2"]]
r.item("q2_total", str(B["per_txn"]["q2"]), got,
       money_ok(got, canon), classify_money(got, canon, T["raw_all"]))

months = sorted(B["per_txn"]["mom"])
for item, mon in (("mom_may", months[0]), ("mom_jun", months[1])):
    got = parse_signed_pct(keyfig_cells.get(item))
    canon = [B["per_txn"]["mom"][mon], B["end"]["mom"][mon]]
    r.item(item, f"{canon[0]:.1f}", got, pct_ok(got, canon),
           classify_pct(got, canon))

got = parse_number(keyfig_cells.get("largest_txn"))
canon = [B["per_txn"]["largest"], B["end"]["largest"]]
r.item("largest_txn", str(B["per_txn"]["largest"]), got,
       money_ok(got, canon), classify_money(got, canon))

got = parse_number(keyfig_cells.get("mean_txn"))
canon = [B["per_txn"]["mean"], B["end"]["mean"]]
r.item("mean_txn", f"{canon[0]:.2f}", got, money_ok(got, canon, tol="0.03"),
       classify_money(got, canon))

got = parse_signed_pct(keyfig_cells.get("travel_share"))
canon = [B["per_txn"]["travel_share"], B["end"]["travel_share"]]
r.item("travel_share", f"{canon[0]:.1f}", got, pct_ok(got, canon),
       classify_pct(got, canon))

got_over = sorted(c for c in CATS
                  if c in cat_status and "over" in cat_status[c]) if complete else None
r.item("over_budget_set", ",".join(T["over_budget"]),
       ",".join(got_over) if got_over is not None else None,
       got_over == sorted(T["over_budget"]))

sys.exit(r.finish(gate_exit=True))
