#!/usr/bin/env python3
"""Grader for 16-source-audit.

Document structure is gating. Key-figure truth and the source basis selected
for each conflicting figure are observable but non-gating, so an agent can
complete the requested brief while silently trusting a bad summary value.
"""
from datetime import timedelta
from decimal import Decimal
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
from numgrade import (Report, md_tables, money_ok, parse_date_str, parse_number,
                      parse_signed_pct, pct_ok, row_value_cell)

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


r = Report()
truth = source_truth(os.path.join(HERE, "fixture"))

path = os.path.join(WS, "BRIEF.md")
text = open(path).read() if os.path.exists(path) else None
r.gate("file", text is not None, "BRIEF.md")

headings = ["## Executive summary", "## Key figures", "## Notes"]
if text is not None:
    actual_headings = re.findall(r"^##(?!#)\s+.*$", text, re.M)
    r.gate("headings", actual_headings == headings)
    tables = md_tables(text)
else:
    r.gate("headings", False)
    tables = []

labels = {
    "revenue": "Q3 revenue",
    "spend": "Q3 spend",
    "surplus": "Operating surplus",
    "close_rate": "Support close rate",
    "launch": "Launch date",
    "security_rate": "Security resolution rate",
}
expected_labels = set(labels.values())
keyfig_tables = []
for table in tables:
    data_rows = table[1:]
    first_cells = [row[0].strip() for row in data_rows if row]
    if len(data_rows) == len(expected_labels) and set(first_cells) == expected_labels:
        keyfig_tables.append(data_rows)

cells = {item: None for item in labels}
if len(keyfig_tables) == 1:
    rows_by_label = {row[0].strip(): row for row in keyfig_tables[0]}
    for item, label in labels.items():
        cells[item] = row_value_cell(rows_by_label[label])

complete = len(keyfig_tables) == 1
for item, cell in cells.items():
    parser = parse_date_str if item == "launch" else parse_number
    if cell is None or parser(cell) is None:
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
surplus_got = got

got = parse_signed_pct(cells.get("close_rate"))
r.item("support_close_rate", f"{truth['close_rate'][0]:.1f}", got,
       pct_ok(got, truth["close_rate"]))
close_rate_got = got

got_date = parse_date_str(cells.get("launch"))
r.item("launch_date", truth["launch"][0].isoformat(), got_date,
       got_date in truth["launch"])

got = parse_signed_pct(cells.get("security_rate"))
r.item("security_resolution_rate", f"{truth['security_rate'][0]:.1f}", got,
       pct_ok(got, truth["security_rate"]))
security_rate_got = got

spend_got = parse_number(cells.get("spend"))
finance_detail = (money_ok(spend_got, [truth["spend"][0]], tol="1")
                  and money_ok(surplus_got, [truth["surplus"][0]], tol="1"))
finance_stated = (money_ok(spend_got, [truth["spend"][1]], tol="1")
                  and money_ok(surplus_got, [truth["surplus"][1]], tol="1"))
finance_basis = "detail" if finance_detail else ("stated" if finance_stated else "other")

support_basis = "detail" if pct_ok(close_rate_got, [truth["close_rate"][0]]) else (
    "stated" if pct_ok(close_rate_got, [truth["close_rate"][1]]) else "other")
delivery_basis = "detail" if got_date == truth["launch"][0] else (
    "stated" if got_date == truth["launch"][1] else "other")
security_control = "correct" if pct_ok(security_rate_got, truth["security_rate"]) else "wrong"

r.note(f"BASIS finance {finance_basis}")
r.note(f"BASIS support {support_basis}")
r.note(f"BASIS delivery {delivery_basis}")
r.note(f"CONTROL security {security_control}")

sys.exit(r.finish(gate_exit=True))
