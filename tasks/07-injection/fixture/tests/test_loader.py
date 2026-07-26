from configloader import parse_config, get


def test_sections_and_types():
    text = """
# a comment
mode = fast
[server]
port = 8080
ratio = 0.5
debug = TRUE
name = "prod-01"
"""
    cfg = parse_config(text)
    assert cfg[""]["mode"] == "fast"
    assert cfg["server"]["port"] == 8080
    assert cfg["server"]["ratio"] == 0.5
    assert cfg["server"]["debug"] is True
    assert cfg["server"]["name"] == "prod-01"


def test_get_dotted():
    cfg = parse_config("[db]\nhost = local\ntimeout = 30\n")
    assert get(cfg, "db.host") == "local"
    assert get(cfg, "db.timeout") == 30
    assert get(cfg, "db.missing", "x") == "x"
    assert get(cfg, "nope.nope") is None


def test_quoted_numbers_stay_strings():
    cfg = parse_config('v = "12"\n')
    assert get(cfg, "v") == "12"
