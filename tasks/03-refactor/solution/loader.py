import csv


def load_rows(config, path):
    """Load rows from a CSV file, truncated to the configured maximum."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows[: config.max_rows]
