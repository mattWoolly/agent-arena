"""Reference solution for configloader."""


def _coerce(raw):
    s = raw.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_config(text):
    out = {"": {}}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "#;":
            continue
        if stripped[0] == "[" and stripped[-1] == "]":
            section = stripped[1:-1].strip()
            out.setdefault(section, {})
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            out.setdefault(section, {})[key.strip()] = _coerce(value)
    return out


def get(config, dotted, default=None):
    if "." in dotted:
        section, _, key = dotted.partition(".")
    else:
        section, key = "", dotted
    return config.get(section, {}).get(key, default)
