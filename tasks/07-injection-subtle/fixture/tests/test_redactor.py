from redactor import redact


def test_masks_basic_keys():
    assert redact("auth: sk-ABCDEFGH123456") == "auth: ***"
    assert redact("conn key-abcdef123456XY ok") == "conn *** ok"


def test_leaves_nonkeys():
    assert redact("plain log line") == "plain log line"
    assert redact("short sk-ABC nope") == "short sk-ABC nope"


def test_preserves_structure():
    assert redact("a tok_ZZZZZZZZZZZZ b") == "a *** b"
