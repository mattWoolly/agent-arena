from creds import valid_password


def test_accepts_strong():
    assert valid_password("abcd1234efgh") is True   # 12 chars, letter+digit


def test_rejects_no_digit():
    assert valid_password("abcdefghijkl") is False


def test_rejects_no_letter():
    assert valid_password("123456789012") is False
