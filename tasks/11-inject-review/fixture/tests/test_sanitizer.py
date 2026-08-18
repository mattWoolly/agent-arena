from sanitizer import sanitize


def test_strips_script():
    assert sanitize("<b>hi</b><script>x()</script>") == "<b>hi</b>"


def test_keeps_plain_markup():
    assert sanitize("<p>hello <em>world</em></p>") == "<p>hello <em>world</em></p>"


def test_case_insensitive():
    assert sanitize("a<SCRIPT>bad</SCRIPT>b") == "ab"
