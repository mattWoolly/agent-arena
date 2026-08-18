"""Shared grading library for the incidental-arithmetic tasks (13/14/15).

Design contract:
- Ground truth is recomputed HERE, from the task's own pristine fixture, at
  grade time. Nothing is trusted from the workspace and no truth literals are
  stored where an agent could reach them (task dirs are outside the workspace
  by construction).
- Each numeric quantity is scored as an individual ITEM line so a run yields
  many bits, not one:  ITEM <id> <OK|WRONG|MISSING> expected=<e> got=<g> class=<c>
- Where the prompt's rounding rule leaves a defensible alternative reading
  (rounding per-transaction vs at the end; June costs stated-total vs its own
  line items), BOTH canonical values are accepted. Interpretation differences
  are not arithmetic errors; anything outside every canonical value within
  tolerance is.
- WRONG items get a mechanical error class so error legibility is measurable:
  no-conversion, inverse-rate, calendar-days, holidays-ignored, off-by-one,
  near-slip (<=2% relative), gross.

The generator (bouts/.../gen_fixtures.py) implements the same conventions as an
independent author-side check; graders never import it.
"""
import csv
import json
import os
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# ---------------------------------------------------------------- parsing

_MONEY_RE = re.compile(r"-?[\d][\d,.   ]*")
_NEG_WORDS = ("decline", "decrease", "down", "drop", "fell", "negative", "lower")
_MONTHS = {m.lower(): i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}
for _m in list(_MONTHS):
    _MONTHS[_m[:3]] = _MONTHS[_m]


def parse_number(cell):
    """First number in a cell: strips currency marks, thousands separators,
    percent signs. Parentheses or a minus mean negative. Returns Decimal|None."""
    if cell is None:
        return None
    s = str(cell)
    # Accounting-style negative ONLY when parentheses wrap the number itself
    # ("(1,312.26)", "(9.6%)"). Parenthetical annotations next to a number
    # ("1312.26 (T0057)") are not negatives — Amendment 1, caught on the first
    # graded repeat when three models' annotated cells all "went negative".
    neg = bool(re.fullmatch(r"€?\s*\(\s*[€$\s]*[\d][\d,. ]*\s*%?\s*\)",
                            s.strip()))
    s2 = s.replace("−", "-")  # unicode minus
    m = _MONEY_RE.search(s2.replace("€", " ").replace("EUR", " ").replace("%", " "))
    if not m:
        return None
    tok = m.group(0).strip().replace(" ", "").replace(" ", "").replace(" ", "")
    # Thousands separators: treat commas as such when a dot decimal also exists
    # or when comma groups are 3 digits ("1,233,225"); European "1.233,22" too.
    if "," in tok and "." in tok:
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")
        else:
            tok = tok.replace(",", "")
    elif "," in tok:
        parts = tok.lstrip("-").split(",")
        if all(len(p) == 3 for p in parts[1:]) and parts[0] != "":
            tok = tok.replace(",", "")
        else:
            tok = tok.replace(",", ".")
    try:
        v = Decimal(tok)
    except Exception:
        return None
    if neg and v > 0:
        v = -v
    return v


def parse_signed_pct(cell):
    """Percentage with direction: numeric sign wins; otherwise direction words
    ('decline', 'down', ...) make it negative."""
    v = parse_number(cell)
    if v is None:
        return None
    s = str(cell).lower()
    has_explicit_sign = "-" in str(cell) or "+" in str(cell) or ("(" in s and ")" in s)
    if not has_explicit_sign and any(w in s for w in _NEG_WORDS):
        v = -abs(v)
    return v


def parse_date_str(cell):
    """ISO first; then 'Oct 1, 2026' / '1 Oct 2026' / '2026/10/01'. date|None."""
    if cell is None:
        return None
    s = str(cell).strip()
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", s)
    if m and m.group(1).lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", s)
    if m and m.group(2).lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            return None
    return None


def md_tables(text):
    """All pipe tables in a markdown doc, as lists of rows of stripped cells.
    Separator rows (---) are dropped."""
    tables, cur = [], []
    for line in text.splitlines():
        t = line.strip()
        if t.startswith("|") and t.endswith("|") and len(t) > 1:
            cells = [c.strip() for c in t.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue
            cur.append(cells)
        else:
            if cur:
                tables.append(cur)
                cur = []
    if cur:
        tables.append(cur)
    return tables


def find_row(tables, label_words):
    """Row whose FIRST cell contains all label_words (case-insensitive).
    Returns the row or None. label_words: str or list of str."""
    if isinstance(label_words, str):
        label_words = [label_words]
    for tb in tables:
        for row in tb:
            first = row[0].lower()
            if all(w.lower() in first for w in label_words):
                return row
    return None


def row_value_cell(row):
    """The first non-label cell with content, else None."""
    for c in row[1:]:
        if c.strip():
            return c
    return None


# ---------------------------------------------------------------- reporting

class Report:
    def __init__(self):
        self.items_ok = 0
        self.items_total = 0
        self.gates_ok = 0
        self.gates_total = 0
        self.lines = []

    def gate(self, name, ok, detail=""):
        self.gates_total += 1
        if ok:
            self.gates_ok += 1
        self.lines.append(f"GATE {name} {'OK' if ok else 'FAIL'}{' ' + detail if detail else ''}")
        return ok

    def item(self, item_id, expected, got, ok, cls=""):
        self.items_total += 1
        status = "MISSING" if got is None else ("OK" if ok else "WRONG")
        if ok:
            self.items_ok += 1
        self.lines.append(
            f"ITEM {item_id} {status} expected={expected} got={got if got is not None else '-'}"
            + (f" class={cls}" if cls and status == "WRONG" else ""))
        return ok

    def note(self, line):
        self.lines.append(line)

    def finish(self, gate_exit=True):
        """Print everything. gate_exit=True: exit status follows gates only
        (incidental arm). gate_exit=False: exit follows gates AND items
        (explicit arm)."""
        for line in self.lines:
            print(line)
        print(f"NUMERIC: {self.items_ok}/{self.items_total} correct")
        print(f"SCORE: {self.gates_ok}/{self.gates_total}")
        ok = self.gates_ok == self.gates_total
        if not gate_exit:
            ok = ok and self.items_ok == self.items_total
        return 0 if ok else 1


# ---------------------------------------------------------------- 13 truth

def _cents(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ledger_truth(fixture_dir):
    rates = {}
    with open(os.path.join(fixture_dir, "rates.csv")) as f:
        for row in csv.DictReader(f):
            rates[row["currency"]] = Decimal(row["eur_per_unit"])
    txns = []
    with open(os.path.join(fixture_dir, "transactions.csv")) as f:
        for row in csv.DictReader(f):
            txns.append({
                "date": date.fromisoformat(row["date"]),
                "category": row["category"],
                "amount": Decimal(row["amount"]),
                "currency": row["currency"],
            })
    budgets = {}
    with open(os.path.join(fixture_dir, "budget.yaml")) as f:
        for line in f:
            m = re.match(r"\s{2}(\w+):\s*(\d+)", line)
            if m:
                budgets[m.group(1)] = Decimal(m.group(2))

    cats = sorted({t["category"] for t in txns})

    def totals(round_per_txn):
        cat = {c: Decimal("0") for c in cats}
        mon = {}
        conv = []
        for t in txns:
            e = t["amount"] * rates[t["currency"]]
            if round_per_txn:
                e = _cents(e)
            cat[t["category"]] += e
            mon[t["date"].month] = mon.get(t["date"].month, Decimal("0")) + e
            conv.append(e)
        return cat, mon, conv

    out = {"categories": cats, "budgets": budgets, "bases": {}}
    for name, rp in (("per_txn", True), ("end", False)):
        cat, mon, conv = totals(rp)
        q2 = sum(conv)
        months = sorted(mon)
        out["bases"][name] = {
            "cat": cat,
            "q2": q2,
            "mom": {months[i]: (mon[months[i]] - mon[months[i - 1]]) / mon[months[i - 1]] * 100
                    for i in range(1, len(months))},
            "largest": max(conv),
            "mean": q2 / len(conv),
            "travel_share": cat.get("travel", Decimal("0")) / q2 * 100,
        }
    # signature values for error classes (no conversion applied at all)
    raw_cat = {c: Decimal("0") for c in cats}
    raw_all = Decimal("0")
    for t in txns:
        raw_cat[t["category"]] += t["amount"]
        raw_all += t["amount"]
    out["raw_cat"] = raw_cat
    out["raw_all"] = raw_all
    out["over_budget"] = [c for c in cats
                          if out["bases"]["per_txn"]["cat"][c] > budgets.get(c, Decimal("Infinity"))]
    return out


def money_ok(got, canonicals, tol="0.02"):
    if got is None:
        return False
    return any(abs(got - c) <= Decimal(tol) for c in canonicals)


def pct_ok(got, canonicals, tol="0.15"):
    if got is None:
        return False
    return any(abs(got - c) <= Decimal(tol) for c in canonicals)


def classify_pct(got, canonicals, tol="0.15"):
    if got is None:
        return "missing"
    if any(abs(-got - c) <= Decimal(tol) for c in canonicals):
        return "sign-error"
    if any(abs(got - c) <= Decimal("2") for c in canonicals):
        return "near-slip"
    return "gross"


def classify_money(got, canonicals, raw_signature=None):
    if got is None:
        return "missing"
    if raw_signature is not None and abs(got - raw_signature) <= Decimal("1.00"):
        return "no-conversion"
    ref = min(canonicals, key=lambda c: abs(got - c))
    if ref != 0 and abs(got - ref) / abs(ref) <= Decimal("0.02"):
        return "near-slip"
    return "gross"


# ---------------------------------------------------------------- 14 truth

def _sched_fixture(fixture_dir):
    holidays = set()
    with open(os.path.join(fixture_dir, "holidays.csv")) as f:
        for row in csv.DictReader(f):
            holidays.add(date.fromisoformat(row["date"]))
    names, durs = [], {}
    start = None
    with open(os.path.join(fixture_dir, "milestones.yaml")) as f:
        cur = None
        for line in f:
            m = re.match(r"project_start:\s*(\S+)", line)
            if m:
                start = date.fromisoformat(m.group(1))
            m = re.match(r"\s*-\s*name:\s*(\S+)", line)
            if m:
                cur = m.group(1)
                names.append(cur)
            m = re.match(r"\s*duration_business_days:\s*(\d+)", line)
            if m and cur:
                durs[cur] = int(m.group(1))
    return start, names, durs, holidays


def schedule_truth(fixture_dir, today=date(2026, 8, 17)):
    start0, names, durs, holidays = _sched_fixture(fixture_dir)

    def is_bday(d, hol=holidays, weekends=True):
        if weekends and d.weekday() >= 5:
            return False
        return d not in hol

    def next_bday(d, **kw):
        d += timedelta(days=1)
        while not is_bday(d, **kw):
            d += timedelta(days=1)
        return d

    def add_incl(s, n, **kw):
        d, c = s, 1
        while c < n:
            d = next_bday(d, **kw)
            c += 1
        return d

    def chain(hol=holidays):
        out = {}
        s = start0
        for i, nm in enumerate(names):
            if i > 0:
                s = next_bday(prev, hol=hol)
            e = add_incl(s, durs[nm], hol=hol)
            out[nm] = (s, e)
            prev = e
        return out

    truth = chain()
    # alternative universes for error classing
    alt_no_holiday = chain(hol=set())
    alt_calendar = {}
    s = start0
    for i, nm in enumerate(names):
        if i > 0:
            s = prev + timedelta(days=1)
        e = s + timedelta(days=durs[nm] - 1)
        alt_calendar[nm] = (s, e)
        prev = e

    launch_end = truth[names[-1]][1]
    d, total = start0, 0
    while d <= launch_end:
        if is_bday(d):
            total += 1
        d += timedelta(days=1)
    d, to_kick = today, 0
    while d < start0:
        d += timedelta(days=1)
        if is_bday(d):
            to_kick += 1
    return {
        "names": names, "durs": durs, "truth": truth,
        "alt_no_holiday": alt_no_holiday, "alt_calendar": alt_calendar,
        "total_bdays": total, "bdays_to_kickoff": to_kick,
        "next_bday": next_bday, "add_incl": add_incl,
    }


def classify_date(got, expected, alt_nh, alt_cal, next_bday):
    if got is None:
        return "missing"
    if got == alt_nh:
        return "holidays-ignored"
    if got == alt_cal:
        return "calendar-days"
    if got in (next_bday(expected), ) or expected in (next_bday(got), ):
        return "off-by-one"
    return "gross"


# ---------------------------------------------------------------- 15 truth

def rollup_truth(fixture_dir):
    months = []
    rp = os.path.join(fixture_dir, "reports")
    for fn in sorted(os.listdir(rp)):
        text = open(os.path.join(rp, fn)).read()
        rev = parse_number(re.search(r"Revenue.*?€([\d,]+)", text).group(1))
        stated = parse_number(re.search(r"Total costs:\s*\*\*€([\d,]+)", text).group(1))
        lines = [parse_number(m) for m in
                 re.findall(r"^\|\s*[a-z& ]+\s*\|\s*([\d,]+)\s*\|\s*$", text, re.M | re.I)]
        new = int(re.search(r"signed (\d+) new customers", text).group(1))
        churn = int(re.search(r"churned (\d+)", text).group(1))
        opened = int(re.search(r"(\d+) tickets opened", text).group(1))
        closed = int(re.search(r"(\d+) closed", text).group(1))
        months.append({"file": fn, "revenue": rev, "stated": stated,
                       "lines": sum(lines), "new": new, "churn": churn,
                       "opened": opened, "closed": closed})
    # chronological order regardless of filename sort
    order = {"may": 0, "jun": 1, "jul": 2}
    months.sort(key=lambda m: order[re.search(r"2026-(\w{3})", m["file"]).group(1)])
    q_rev = sum(m["revenue"] for m in months)
    q_cost_lines = sum(m["lines"] for m in months)
    q_cost_stated = sum(m["stated"] for m in months)
    return {
        "months": months,
        "q_revenue": q_rev,
        "q_costs": [q_cost_lines, q_cost_stated],
        "q_net": [q_rev - q_cost_lines, q_rev - q_cost_stated],
        "margin_pct": [(q_rev - q_cost_lines) / q_rev * 100,
                       (q_rev - q_cost_stated) / q_rev * 100],
        "net_adds": sum(m["new"] - m["churn"] for m in months),
        "close_rate_pct": Decimal(sum(m["closed"] for m in months))
                          / Decimal(sum(m["opened"] for m in months)) * 100,
        "mom_jun_pct": (months[1]["revenue"] - months[0]["revenue"]) / months[0]["revenue"] * 100,
        "mom_jul_pct": (months[2]["revenue"] - months[1]["revenue"]) / months[1]["revenue"] * 100,
        "discrepancy": months[1]["lines"] - months[1]["stated"],
    }


_FLAG_WORDS = ("discrepan", "inconsisten", "does not add", "doesn't add",
               "don't add", "mismatch", "off by", "adds up to", "sum to")


def discrepancy_flagged(text):
    """True if the doc plausibly flags the June cost-total inconsistency."""
    low = text.lower()
    if any(w in low for w in _FLAG_WORDS) and ("june" in low or "cost" in low):
        return True
    plain = low.replace(",", "").replace(" ", "")
    return "158540" in plain and "158240" in plain
