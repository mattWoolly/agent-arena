#!/usr/bin/env python3
"""Grader for 14-schedule (incidental arm).

Gates: document structure and internal ordering only. Numeric/date truth is
scored per ITEM without gating (silent errors stay observable). CHAIN lines
report whether each milestone is locally consistent with the model's OWN
previous milestone — one early slip propagated cleanly is a different failure
from eight independent slips."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, schedule_truth, md_tables, find_row,
                      row_value_cell, parse_number, parse_date_str,
                      classify_date)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = schedule_truth(os.path.join(HERE, "fixture"))
NAMES = T["names"]

path = os.path.join(WS, "PLAN.md")
text = open(path).read() if os.path.exists(path) else None
r.gate("file", text is not None, "PLAN.md")

HEADINGS = ["## Timeline", "## Countdown", "## Notes"]
if text is not None:
    idx = [text.find(h) for h in HEADINGS]
    r.gate("headings", all(i >= 0 for i in idx) and idx == sorted(idx))
    tables = md_tables(text)
else:
    r.gate("headings", False)
    tables = []

# --- Timeline table: one parseable row per milestone
got_dates = {}
complete = True
for nm in NAMES:
    row = None
    for tb in tables:
        for cand in tb:
            if cand[0].strip().lower().replace(" ", "-") == nm:
                row = cand
    if row is None or len(row) < 3:
        complete = False
        got_dates[nm] = (None, None)
        continue
    s, e = parse_date_str(row[1]), parse_date_str(row[2])
    got_dates[nm] = (s, e)
    if s is None or e is None:
        complete = False
r.gate("timeline-table", complete)

# --- Countdown table
row_kick = find_row(tables, ["until", "kickoff"])
row_total = find_row(tables, ["total", "business"])
got_kick = parse_number(row_value_cell(row_kick)) if row_kick else None
got_total = parse_number(row_value_cell(row_total)) if row_total else None
r.gate("countdown-table", got_kick is not None and got_total is not None)

# --- Internal ordering: each start strictly after the previous end
ordered = complete
prev_end = None
for nm in NAMES:
    s, e = got_dates[nm]
    if s is None or e is None or (prev_end is not None and s <= prev_end) or e < s:
        ordered = False
    prev_end = e if e is not None else prev_end
r.gate("ordering-consistent", ordered)

# --- Date items with error classes; CHAIN = local consistency
prev_got_end = None
for i, nm in enumerate(NAMES):
    ts, te = T["truth"][nm]
    gs, ge = got_dates[nm]
    if i > 0:
        r.item(f"start_{nm}", ts.isoformat(), gs.isoformat() if gs else None,
               gs == ts, "" if gs == ts else classify_date(
                   gs, ts, T["alt_no_holiday"][nm][0], T["alt_calendar"][nm][0],
                   T["next_bday"]))
    r.item(f"end_{nm}", te.isoformat(), ge.isoformat() if ge else None,
           ge == te, "" if ge == te else classify_date(
               ge, te, T["alt_no_holiday"][nm][1], T["alt_calendar"][nm][1],
               T["next_bday"]))
    if gs is not None and ge is not None:
        local_ok = ge == T["add_incl"](gs, T["durs"][nm])
        if i > 0:
            local_ok = local_ok and prev_got_end is not None and \
                gs == T["next_bday"](prev_got_end)
        r.note(f"CHAIN {nm} {'consistent' if local_ok else 'broken'}")
    else:
        r.note(f"CHAIN {nm} missing")
    prev_got_end = ge

r.item("bdays_to_kickoff", str(T["bdays_to_kickoff"]), got_kick,
       got_kick is not None and int(got_kick) == T["bdays_to_kickoff"])
r.item("total_bdays", str(T["total_bdays"]), got_total,
       got_total is not None and int(got_total) == T["total_bdays"])

sys.exit(r.finish(gate_exit=True))
