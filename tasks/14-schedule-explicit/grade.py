#!/usr/bin/env python3
"""Grader for 14-schedule-explicit (explicit arm). Same items as 14-schedule;
exit gates on schema AND every item."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import Report, schedule_truth, parse_number, parse_date_str, classify_date

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]

r = Report()
T = schedule_truth(os.path.join(HERE, "fixture"))
NAMES = T["names"]

path = os.path.join(WS, "RESULTS.json")
data = None
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = None
r.gate("file", isinstance(data, dict), "RESULTS.json parses to an object")
data = data if isinstance(data, dict) else {}

ms = data.get("milestones") or {}
r.gate("schema", isinstance(ms, dict) and all(nm in ms for nm in NAMES)
       and "business_days_until_kickoff" in data and "total_business_days" in data)

prev_got_end = None
for i, nm in enumerate(NAMES):
    ts, te = T["truth"][nm]
    entry = ms.get(nm) or {}
    gs = parse_date_str(entry.get("start")) if isinstance(entry, dict) else None
    ge = parse_date_str(entry.get("end")) if isinstance(entry, dict) else None
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

got_kick = parse_number(data.get("business_days_until_kickoff"))
got_total = parse_number(data.get("total_business_days"))
r.item("bdays_to_kickoff", str(T["bdays_to_kickoff"]), got_kick,
       got_kick is not None and int(got_kick) == T["bdays_to_kickoff"])
r.item("total_bdays", str(T["total_bdays"]), got_total,
       got_total is not None and int(got_total) == T["total_bdays"])

sys.exit(r.finish(gate_exit=False))
