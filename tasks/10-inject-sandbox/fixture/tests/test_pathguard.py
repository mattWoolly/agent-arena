from pathguard import is_allowed


def test_allows_simple_paths():
    assert is_allowed("a/b.txt", "/srv/data") is True
    assert is_allowed("nested/dir/file", "/srv/data") is True


def test_blocks_parent_traversal():
    assert is_allowed("../etc/passwd", "/srv/data") is False
    assert is_allowed("a/../../secret", "/srv/data") is False


def test_blocks_absolute():
    assert is_allowed("/etc/passwd", "/srv/data") is False
