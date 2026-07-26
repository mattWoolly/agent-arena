import pytest

from sheet import evaluate, CycleError


def test_left_assoc_subtraction():
    assert evaluate({"A": "=2-3-4"})["A"] == -5.0


def test_left_assoc_division():
    assert evaluate({"A": "=100/5/2"})["A"] == 10.0


def test_parens_override_precedence():
    assert evaluate({"A": "=(1+2)*3"})["A"] == 9.0
    assert evaluate({"A": "=2*(3+4)*5"})["A"] == 70.0


def test_unary_minus_forms():
    assert evaluate({"A": "=-3+ -2"})["A"] == -5.0
    assert evaluate({"A": "=-(2+3)"})["A"] == -5.0
    assert evaluate({"A": "=3- -2"})["A"] == 5.0


def test_forward_reference():
    assert evaluate({"A": "=B+1", "B": "=3"})["A"] == 4.0


def test_shared_subexpression_resolves_once():
    out = evaluate({"A": "=10", "B": "=A*2", "C": "=A+B"})
    assert out["C"] == 30.0


def test_multiletter_and_digit_names():
    out = evaluate({"TOTAL": "=X12+Y", "X12": "=3", "Y": "4"})
    assert out["TOTAL"] == 7.0


def test_self_cycle():
    with pytest.raises(CycleError):
        evaluate({"A": "=A+1"})


def test_mutual_cycle():
    with pytest.raises(CycleError):
        evaluate({"A": "=B", "B": "=A"})


def test_transitive_cycle():
    with pytest.raises(CycleError):
        evaluate({"A": "=B", "B": "=C", "C": "=A"})


def test_division_is_real():
    assert evaluate({"A": "=3/2"})["A"] == 1.5


def test_division_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        evaluate({"A": "=1/0"})


def test_deep_chain_no_recursion_blowup():
    cells = {"C0": "1"}
    for i in range(1, 200):
        cells[f"C{i}"] = f"=C{i-1}+1"
    assert evaluate(cells)["C199"] == 200.0
