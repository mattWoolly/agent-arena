import dataclasses
import json


@dataclasses.dataclass(frozen=True)
class Config:
    title: str = "Report"
    output_format: str = "text"  # "text" or "markdown"
    max_rows: int = 10
    include_summary: bool = True


def load_config(path):
    """Load config from a JSON file, filling in defaults for missing keys."""
    with open(path) as f:
        raw = json.load(f)
    known = {f.name for f in dataclasses.fields(Config)}
    for key in raw:
        if key not in known:
            raise ValueError(f"unknown config key: {key}")
    return Config(**raw)
