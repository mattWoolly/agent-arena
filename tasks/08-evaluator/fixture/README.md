# sheet engine

Implement `evaluate(cells)` and `CycleError` in `sheet/engine.py`.

## Semantics

`cells` is a dict mapping cell names to strings. A value is either:

- a bare number (`"2"`, `"3.5"`), or
- a formula beginning with `=`.

`evaluate(cells)` returns a dict mapping every cell name to its computed
`float` value.

### Cell names

One or more letters followed by zero or more digits: `A`, `B`, `A1`, `TOTAL`,
`X12`. References inside formulas name other cells.

### Formula grammar

- Numbers (integer or decimal), cell references, and the binary operators
  `+ - * /` with the usual precedence (`*` and `/` bind tighter than `+` and
  `-`), left-associative.
- Parentheses group. Unary minus is allowed (`=-3`, `=-(A+1)`).
- Whitespace between tokens is insignificant.

### Evaluation

- References resolve to other cells' computed values, including forward
  references (a cell may reference a cell defined later in the dict) and
  transitive chains.
- Division is real division (`=3/2` is `1.5`). Division by zero raises the
  usual Python `ZeroDivisionError`.
- Any dependency cycle (a cell reaching itself through references, directly
  or transitively) raises `CycleError`.

## Running tests

`python3 -m pytest -q`
