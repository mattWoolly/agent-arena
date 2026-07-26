from sheet import evaluate


def test_number_and_add():
    assert evaluate({"A": "2", "B": "=A+3"})["B"] == 5.0


def test_precedence():
    assert evaluate({"A": "=1+2*3"})["A"] == 7.0


def test_reference_chain():
    out = evaluate({"A": "=B", "B": "=C", "C": "10"})
    assert out["A"] == 10.0
