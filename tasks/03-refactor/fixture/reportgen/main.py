from .config import load_config
from .formatter import format_report
from .loader import load_rows


def generate(config_path, data_path):
    """End-to-end: load config, load data, render the report string."""
    config = load_config(config_path)
    rows = load_rows(config, data_path)
    return format_report(config, rows)
