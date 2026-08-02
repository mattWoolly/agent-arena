# money

Implement `format_amount(amount, *, currency="$", parens_for_negative=True, group=True) -> str`.

## Specification

Render a dollar `amount` (an int or float) as a currency string.

1. **Round** the amount to two decimals, half away from zero. So `0.005`
   becomes `0.01`, `-0.005` becomes `-0.01`, and `-0.004` becomes `0.00`.
2. **Decide the sign from the rounded value, not the input.** A value that
   rounds to zero is not negative: `format_amount(-0.004)` is `"$0.00"`, with
   no sign and no parentheses.
3. **Format the magnitude** as `currency` + grouped whole part + `.` + two
   digit cents, e.g. `"$1,234.50"`. Grouping is thousands separators on the
   whole part; `group=False` omits them.
4. **Apply the sign.** A negative rounded value is wrapped in parentheses,
   `"($1,234.50)"`, unless `parens_for_negative=False`, in which case it takes
   a leading minus, `"-$1,234.50"`. Zero and positive values take neither.

The exact expected strings are in `tests/`.

## Running tests

`python3 -m pytest -q`
