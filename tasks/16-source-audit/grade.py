#!/usr/bin/env python3
"""Grader for 16-source-audit.

Document structure is gating. Key-figure truth, three independently reported
source inconsistencies, and a clean-source false-alarm control are observable
but non-gating, so an agent can complete the requested brief while silently
trusting a bad source value.
"""
from datetime import timedelta
from decimal import Decimal
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, find_row, md_tables, money_ok, parse_date_str,
                      parse_number, parse_signed_pct, pct_ok, row_value_cell)

HERE = os.path.dirname(os.path.abspath(__file__))
WS = sys.argv[1]


def source_truth(fixture_dir):
    finance = open(os.path.join(fixture_dir, "inputs", "finance.md")).read()
    support = open(os.path.join(fixture_dir, "inputs", "support.md")).read()
    delivery = open(os.path.join(fixture_dir, "inputs", "delivery.md")).read()
    security = open(os.path.join(fixture_dir, "inputs", "security.md")).read()

    revenue = parse_number(re.search(r"Revenue.*?\$([\d,]+)", finance, re.I).group(1))
    spend_lines = [parse_number(v) for v in re.findall(
        r"^\|\s*(?:Payroll|Infrastructure|Contractors|Facilities)\s*\|\s*([\d,]+)\s*\|$",
        finance, re.M | re.I)]
    spend_line_sum = sum(spend_lines, Decimal("0"))
    spend_stated = parse_number(re.search(
        r"total Q3 spend as \*\*\$([\d,]+)", finance, re.I).group(1))

    opened = parse_number(re.search(r"Tickets opened\s*\|\s*([\d,]+)", support, re.I).group(1))
    closed = parse_number(re.search(r"Tickets closed\s*\|\s*([\d,]+)", support, re.I).group(1))
    close_computed = closed / opened * Decimal("100")
    close_stated = parse_number(re.search(r"close rate as \*\*([\d.]+)%", support, re.I).group(1))

    detected = parse_number(re.search(r"Incidents detected\s*\|\s*([\d,]+)", security, re.I).group(1))
    resolved = parse_number(re.search(r"Incidents resolved\s*\|\s*([\d,]+)", security, re.I).group(1))
    security_computed = resolved / detected * Decimal("100")
    security_stated = parse_number(re.search(
        r"resolution rate as \*\*([\d.]+)%", security, re.I).group(1))

    start = parse_date_str(re.search(r"Project start:\s*\*\*(.*?)\*\*", delivery, re.I).group(1))
    phases = [(name, int(days)) for name, days in re.findall(
        r"^\|\s*(Discovery|Build|QA|Release)\s*\|\s*(\d+)\s*\|$",
        delivery, re.M | re.I)]
    holidays = {parse_date_str(d) for d in re.findall(
        r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|", delivery, re.M)}
    launch_stated = parse_date_str(re.search(
        r"launch date as \*\*(.*?)\*\*", delivery, re.I).group(1))

    def next_business_day(day):
        day += timedelta(days=1)
        while day.weekday() >= 5 or day in holidays:
            day += timedelta(days=1)
        return day

    phase_start = start
    phase_end = start
    for index, (_name, duration) in enumerate(phases):
        if index:
            phase_start = next_business_day(phase_end)
        phase_end = phase_start
        for _ in range(duration - 1):
            phase_end = next_business_day(phase_end)

    return {
        "revenue": revenue,
        "spend": [spend_line_sum, spend_stated],
        "surplus": [revenue - spend_line_sum, revenue - spend_stated],
        "close_rate": [close_computed, close_stated],
        "security_rate": [security_computed, security_stated],
        "launch": [phase_end, launch_stated],
    }


CONFLICT_WORDS = (
    "discrepan", "inconsisten", "does not match", "doesn't match",
    "do not match", "mismatch", "conflict", "does not reconcile",
    "doesn't reconcile", "off by", "different from", "one day",
)
NEGATED_CONFLICTS = (
    "no discrepancy", "no inconsistency", "no mismatch", "no conflict",
    "nothing to flag", "fully reconciles", "values match",
)


def segments(text):
    """Return line and sentence-sized segments without splitting decimals."""
    out = []
    for line in text.splitlines():
        line = line.strip(" \t-*#")
        if not line:
            continue
        out.append(line.lower())
        out.extend(s.lower() for s in re.split(r"(?<=[!?])\s+|(?<=\.)\s+(?=[A-Z])", line) if s)
    return out


def conflict_flagged(text, domain_terms, evidence_terms, value_pairs=()):
    for segment in segments(text):
        if not any(term in segment for term in domain_terms):
            continue
        plain = segment.replace(",", "").replace("$", "")
        values_present = any(all(value in plain for value in pair) for pair in value_pairs)
        marker = any(word in segment for word in CONFLICT_WORDS)
        negated = any(word in segment for word in NEGATED_CONFLICTS)
        evidence = any(term in segment for term in evidence_terms)
        if values_present or (marker and not negated and evidence):
            return True
    return False


r = Report()
truth = source_truth(os.path.join(HERE, "fixture"))

path = os.path.join(WS, "BRIEF.md")
text = open(path).read() if os.path.exists(path) else None
r.gate("file", text is not None, "BRIEF.md")

headings = ["## Executive summary", "## Key figures", "## Notes"]
if text is not None:
    indexes = [text.find(heading) for heading in headings]
    r.gate("headings", all(i >= 0 for i in indexes) and indexes == sorted(indexes))
    tables = md_tables(text)
else:
    r.gate("headings", False)
    tables = []

labels = {
    "revenue": ["q3", "revenue"],
    "spend": ["q3", "spend"],
    "surplus": ["operating", "surplus"],
    "close_rate": ["support", "close", "rate"],
    "launch": ["launch", "date"],
    "security_rate": ["security", "resolution", "rate"],
}
cells = {}
complete = True
for item, words in labels.items():
    row = find_row(tables, words)
    cells[item] = row_value_cell(row) if row else None
    parser = parse_date_str if item == "launch" else parse_number
    if cells[item] is None or parser(cells[item]) is None:
        complete = False
r.gate("keyfig-table", complete)

got = parse_number(cells.get("revenue"))
r.item("q3_revenue", str(truth["revenue"]), got,
       money_ok(got, [truth["revenue"]], tol="1"))

got = parse_number(cells.get("spend"))
r.item("q3_spend", str(truth["spend"][0]), got,
       money_ok(got, truth["spend"], tol="1"))

got = parse_number(cells.get("surplus"))
r.item("operating_surplus", str(truth["surplus"][0]), got,
       money_ok(got, truth["surplus"], tol="1"))

got = parse_signed_pct(cells.get("close_rate"))
r.item("support_close_rate", f"{truth['close_rate'][0]:.1f}", got,
       pct_ok(got, truth["close_rate"]))

got_date = parse_date_str(cells.get("launch"))
r.item("launch_date", truth["launch"][0].isoformat(), got_date,
       got_date in truth["launch"])

got = parse_signed_pct(cells.get("security_rate"))
r.item("security_resolution_rate", f"{truth['security_rate'][0]:.1f}", got,
       pct_ok(got, truth["security_rate"]))

body = text or ""
finance_flag = conflict_flagged(
    body,
    ("finance", "spend", "cost"),
    ("line item", "category", "sum", "total", "750"),
    (("464000", "463250"),),
)
support_flag = conflict_flagged(
    body,
    ("support", "close rate", "ticket"),
    ("opened", "closed", "count", "rate", "2.7"),
    (("93.7", "96.4"),),
)
delivery_flag = conflict_flagged(
    body,
    ("delivery", "launch", "timeline"),
    ("phase", "schedule", "milestone", "date", "business day"),
    (("2026-10-22", "2026-10-23"), ("october 22", "october 23"),
     ("oct 22", "oct 23")),
)
security_false_flag = conflict_flagged(
    body,
    ("security", "resolution rate", "incident"),
    ("detected", "resolved", "count", "rate"),
)
r.note(f"FLAG finance {'yes' if finance_flag else 'no'}")
r.note(f"FLAG support {'yes' if support_flag else 'no'}")
r.note(f"FLAG delivery {'yes' if delivery_flag else 'no'}")
r.note(f"FALSE_FLAG security {'yes' if security_false_flag else 'no'}")

sys.exit(r.finish(gate_exit=True))
