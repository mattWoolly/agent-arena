from money import format_amount as f


def test_positive_grouping():
    assert f(1234.5) == "$1,234.50"


def test_negative_parens():
    assert f(-1234.5) == "($1,234.50)"


def test_small_negative_rounds_to_zero():
    # -0.004 rounds to 0.00; a value that rounds to zero is not negative.
    assert f(-0.004) == "$0.00"


def test_negative_half_away_from_zero():
    assert f(-0.005) == "($0.01)"


def test_positive_half_away_from_zero():
    assert f(0.005) == "$0.01"


def test_zero():
    assert f(0) == "$0.00"


def test_negative_zero_float():
    assert f(-0.0) == "$0.00"


def test_millions_grouping():
    assert f(1000000) == "$1,000,000.00"


def test_minus_option():
    assert f(-5, parens_for_negative=False) == "-$5.00"


def test_no_group_option():
    assert f(1234.5, group=False) == "$1234.50"


def test_rounding_boundaries():
    assert f(0.994) == "$0.99"
    assert f(0.995) == "$1.00"
