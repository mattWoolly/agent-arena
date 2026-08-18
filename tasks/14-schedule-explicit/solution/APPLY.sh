#!/usr/bin/env bash
# Reference solution: writes a correct RESULTS.json into $WS.
set -eu
python3 - "$WS" <<'PY'
import csv, json, re, sys
from datetime import date, timedelta
ws = sys.argv[1]
hol = {date.fromisoformat(r["date"]) for r in csv.DictReader(open(f"{ws}/holidays.csv"))}
names, durs, start0, cur = [], {}, None, None
for line in open(f"{ws}/milestones.yaml"):
    if m := re.match(r"project_start:\s*(\S+)", line):
        start0 = date.fromisoformat(m.group(1))
    if m := re.match(r"\s*-\s*name:\s*(\S+)", line):
        cur = m.group(1); names.append(cur)
    if (m := re.match(r"\s*duration_business_days:\s*(\d+)", line)) and cur:
        durs[cur] = int(m.group(1))
bday = lambda d: d.weekday() < 5 and d not in hol
def nxt(d):
    d += timedelta(days=1)
    while not bday(d): d += timedelta(days=1)
    return d
sched, s = {}, start0
for i, nm in enumerate(names):
    if i: s = nxt(prev)
    e, c = s, 1
    while c < durs[nm]: e = nxt(e); c += 1
    sched[nm] = (s, e); prev = e
launch = sched[names[-1]][1]
d, total = start0, 0
while d <= launch:
    if bday(d): total += 1
    d += timedelta(days=1)
d, kick = date(2026, 8, 17), 0
while d < start0:
    d += timedelta(days=1)
    if bday(d): kick += 1
json.dump({
    "milestones": {nm: {"start": sched[nm][0].isoformat(),
                        "end": sched[nm][1].isoformat()} for nm in names},
    "business_days_until_kickoff": kick,
    "total_business_days": total,
}, open(f"{ws}/RESULTS.json", "w"), indent=2)
PY
