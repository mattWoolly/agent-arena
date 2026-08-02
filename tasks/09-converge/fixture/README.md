# money

Implement `format_amount(amount, *, currency="$", parens_for_negative=True, group=True) -> str`.

## Specification

Render a dollar `amount` (an int or float) as a currency string.

1. **Round** the amount to two decimals, half away from zero. So `0.005`
   becomes `0.01` and `-0.005` becomes `-0.01`.
2. **Format the magnitude** as `currency` + grouped whole part + `.` + two
   digit cents, e.g. `"$1,234.50"`. Grouping is thousands separators on the
   whole part; `group=False` omits them.
3. **Apply the sign.** A negative value is wrapped in parentheses,
   `"($1,234.50)"`, unless `parens_for_negative=False`, in which case it takes
   a leading minus, `"-$1,234.50"`. Zero and positive values take neither.

The exact expected strings, including the edge cases, are in `tests/`. The
tests are the specification; make them all pass.

## Running tests

`python3 -m pytest -q`
