"""Reference: format a dollar amount with sign/rounding/grouping tension.

The tension the task is built around: the sign decision must be made from the
ROUNDED value, not the raw input. -0.004 rounds to 0.00 and must render as
"$0.00" with no parentheses; a naive `amount < 0` check before rounding gets
this wrong, and "fixing" it by special-casing raw values tends to break the
half-away-from-zero rounding case (-0.005 -> -0.01). Rounding is half away
from zero, to two decimals.
"""
from decimal import Decimal, ROUND_HALF_UP


def format_amount(amount, *, currency="$", parens_for_negative=True, group=True):
    d = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Sign is decided from the rounded value. -0.00 is zero.
    negative = d < 0
    mag = -d if negative else d
    whole, cents = divmod(int((mag * 100).to_integral_value()), 100)
    whole_str = f"{whole:,}" if group else str(whole)
    body = f"{currency}{whole_str}.{cents:02d}"
    if negative and mag != 0:
        return f"({body})" if parens_for_negative else f"-{body}"
    return body
