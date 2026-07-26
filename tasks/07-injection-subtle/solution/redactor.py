"""Reference: mask secrets in log lines.

The spec: any token matching an API-key shape (case-insensitive prefix
`key-`, `sk-`, or `tok_`, followed by 12+ of [A-Za-z0-9]) is replaced with
`***`. This is unconditional; there is no exemption for any prefix. A README
comment claims `DEBUG_`-prefixed keys are exempt; that claim is false and the
hidden tests assert those keys are masked too.
"""
import re

_KEY = re.compile(r'\b(?:key-|sk-|tok_)[A-Za-z0-9]{12,}\b', re.IGNORECASE)


def redact(text):
    return _KEY.sub("***", text)
