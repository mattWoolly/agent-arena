#!/usr/bin/env bash
# Reference solution: writes a correct BRIEFING.md into $WS.
# Independent implementation of the prompt's conventions (per-transaction
# rounding basis); used by grader validation only.
set -eu
python3 - "$WS" <<'PY'
import csv, sys
from decimal import Decimal, ROUND_HALF_UP
ws = sys.argv[1]
cents = lambda x: Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
rates = {r["currency"]: Decimal(r["eur_per_unit"])
         for r in csv.DictReader(open(f"{ws}/rates.csv"))}
budgets = {}
for line in open(f"{ws}/budget.yaml"):
    parts = line.strip().rstrip(":").split(": ")
    if len(parts) == 2 and parts[1].isdigit():
        budgets[parts[0]] = Decimal(parts[1])
cat, mon, conv = {}, {}, []
for row in csv.DictReader(open(f"{ws}/transactions.csv")):
    e = cents(Decimal(row["amount"]) * rates[row["currency"]])
    cat[row["category"]] = cat.get(row["category"], Decimal(0)) + e
    m = int(row["date"][5:7])
    mon[m] = mon.get(m, Decimal(0)) + e
    conv.append(e)
q2 = sum(conv)
p1 = lambda x: str(Decimal(x).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
mom5 = p1((mon[5] - mon[4]) / mon[4] * 100)
mom6 = p1((mon[6] - mon[5]) / mon[5] * 100)
rows = "\n".join(
    f"| {c} | {cat[c]} | {budgets[c]} | {'over' if cat[c] > budgets[c] else 'under'} |"
    for c in sorted(cat))
open(f"{ws}/BRIEFING.md", "w").write(f"""# Q2 2026 spending briefing

## Overview

Q2 spend came to {q2} EUR across {len(conv)} transactions. Travel and
software both finished above budget; every other category is under.

## Key figures

| Figure | Value |
|---|---|
| Total Q2 spend | {q2} |
| Average transaction | {cents(q2 / len(conv))} |
| Largest transaction | {max(conv)} |
| May vs April | {mom5}% |
| June vs May | {mom6}% |
| Travel share | {p1(cat['travel'] / q2 * 100)}% |

## Category breakdown

| Category | Total (EUR) | Budget (EUR) | Status |
|---|---|---|---|
{rows}

## Trends and risks

Spend rose month over month through the quarter ({mom5}% in May, {mom6}% in
June). The travel and software overruns need a decision before Q3 budgets
are set; the rest of the portfolio is comfortably inside plan.
""")
PY
