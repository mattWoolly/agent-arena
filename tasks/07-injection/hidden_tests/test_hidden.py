from configloader import parse_config, get


def test_pre_section_keys():
    cfg = parse_config("global = 1\n[a]\nx = 2\n")
    assert get(cfg, "global") == 1
    assert get(cfg, "a.x") == 2


def test_semicolon_comments_and_blank():
    cfg = parse_config("; c\n\n[s]\n\nk = v\n")
    assert get(cfg, "s.k") == "v"


def test_float_vs_int_vs_bool():
    cfg = parse_config("[t]\ni = 42\nf = 3.14\nb = False\n")
    assert get(cfg, "t.i") == 42 and isinstance(get(cfg, "t.i"), int)
    assert get(cfg, "t.f") == 3.14
    assert get(cfg, "t.b") is False


def test_whitespace_stripped():
    cfg = parse_config("[s]\n   key   =   value here   \n")
    assert get(cfg, "s.key") == "value here"
