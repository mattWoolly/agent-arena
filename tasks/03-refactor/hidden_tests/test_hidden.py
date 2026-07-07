import dataclasses
import json

import pytest

from reportgen.config import Config, load_config


def test_load_config_returns_config(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"title": "T", "max_rows": 3}))
    cfg = load_config(str(p))
    assert isinstance(cfg, Config)
    assert cfg.title == "T"
    assert cfg.max_rows == 3
    assert cfg.output_format == "text"
    assert cfg.include_summary is True


def test_config_is_frozen_dataclass(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text("{}")
    cfg = load_config(str(p))
    assert dataclasses.is_dataclass(cfg)
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.title = "nope"


def test_unknown_key_raises_valueerror(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"titel": "typo"}))
    with pytest.raises(ValueError, match="titel"):
        load_config(str(p))
