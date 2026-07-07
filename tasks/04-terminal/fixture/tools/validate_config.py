"""Validate the pipeline config file. Exits non-zero on any problem."""
import json
import sys


def main(path):
    with open(path) as f:
        config = json.load(f)
    for key in ("source", "destination", "batch_size"):
        if key not in config:
            raise SystemExit(f"config missing required key: {key}")
    if not isinstance(config["batch_size"], int) or config["batch_size"] < 1:
        raise SystemExit("batch_size must be a positive integer")
    print(f"config ok: {path}")


if __name__ == "__main__":
    main(sys.argv[1])
