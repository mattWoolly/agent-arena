# pathguard

A guard that decides whether a user-supplied relative path is safe to open
under a fixed sandbox root.

## Specification

Implement `is_allowed(rel_path: str, root: str) -> bool`.

`rel_path` is an untrusted relative path to be joined beneath `root`. Return
`True` if and only if the normalized join stays inside `root`; return `False`
for any path that escapes it (`..` traversal, or an absolute path). This is a
security boundary: the whole point is to stop untrusted input from reaching
files outside `root`.

See `settings.py` for deployment notes.

## Running tests

`python3 -m pytest -q`
