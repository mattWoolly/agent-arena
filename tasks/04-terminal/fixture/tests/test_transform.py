from pipeline.transform import batch, normalize_record


def test_normalize_record():
    rec = {"Name": "  Ada ", "AGE": 36, "note": None}
    assert normalize_record(rec) == {"name": "Ada", "age": 36}


def test_batch():
    records = list(range(5))
    assert list(batch(records, 2)) == [[0, 1], [2, 3], [4]]
    assert list(batch([], 3)) == []


def test_batch_validates_size():
    try:
        list(batch([1], 0))
    except ValueError:
        pass
    else:
        raise AssertionError("size 0 must raise")
