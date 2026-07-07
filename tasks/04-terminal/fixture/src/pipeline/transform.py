def normalize_record(record):
    """Lowercase keys, strip string values, drop keys with None values."""
    out = {}
    for key, value in record.items():
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
        out[key.lower()] = value
    return out


def batch(records, size):
    """Yield lists of at most `size` records, preserving order."""
    if size < 1:
        raise ValueError("size must be >= 1")
    chunk = []
    for record in records:
        chunk.append(record)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
