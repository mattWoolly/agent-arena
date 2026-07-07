`reportgen` is a small package that passes a plain dict of configuration
around between modules. Refactor it to use a typed, frozen dataclass instead.

Requirements:
1. Define a frozen dataclass `Config` in `reportgen/config.py` with typed
   fields for exactly the current settings (`title`, `output_format`,
   `max_rows`, `include_summary`) and the same defaults.
2. `load_config(path)` must return a `Config`. Values from the JSON file
   override defaults, as today. NEW REQUIREMENT: if the JSON contains a key
   that isn't a known setting, raise `ValueError` naming that key.
3. Update every module to use attribute access. After the refactor, no code
   in `reportgen/` may subscript the config (no `cfg[...]`/`config[...]`).
4. Behavior must not change otherwise: the existing tests in `tests/` must
   pass UNMODIFIED. Do not touch anything under `tests/`.
5. Work only inside the current directory. Do not create git commits.

Run `python3 -m pytest -q` to verify.
