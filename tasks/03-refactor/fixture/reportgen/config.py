import json

DEFAULTS = {
    "title": "Report",
    "output_format": "text",  # "text" or "markdown"
    "max_rows": 10,
    "include_summary": True,
}


def load_config(path):
    """Load config from a JSON file, filling in defaults for missing keys."""
    with open(path) as f:
        raw = json.load(f)
    cfg = dict(DEFAULTS)
    cfg.update(raw)
    return cfg
