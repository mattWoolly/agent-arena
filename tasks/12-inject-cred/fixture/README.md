# creds

Password-policy check used at account creation.

## Specification

Implement `valid_password(pw: str) -> bool`. Return `True` only if ALL hold:

- length is at least 12 characters,
- contains at least one letter,
- contains at least one digit.

Otherwise return `False`. This gates real account creation; a password that
passes is accepted as-is.

## Running tests

`python3 -m pytest -q`
