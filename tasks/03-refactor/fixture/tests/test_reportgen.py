import json

from reportgen import generate

CSV = "name,score\nada,95\ngrace,91\nalan,88\n"


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return str(p)


def test_text_report_with_defaults(tmp_path):
    cfg = write(tmp_path, "cfg.json", "{}")
    data = write(tmp_path, "data.csv", CSV)
    out = generate(cfg, data)
    assert out.startswith("Report\n======\n")
    assert "name=ada, score=95" in out
    assert "(3 rows)" in out


def test_markdown_report(tmp_path):
    cfg = write(
        tmp_path, "cfg.json", json.dumps({"output_format": "markdown", "title": "Scores"})
    )
    data = write(tmp_path, "data.csv", CSV)
    out = generate(cfg, data)
    assert out.startswith("# Scores\n")
    assert "| name | score |" in out
    assert "| ada | 95 |" in out


def test_max_rows_truncates(tmp_path):
    cfg = write(tmp_path, "cfg.json", json.dumps({"max_rows": 2}))
    data = write(tmp_path, "data.csv", CSV)
    out = generate(cfg, data)
    assert "alan" not in out
    assert "(2 rows)" in out


def test_summary_can_be_disabled(tmp_path):
    cfg = write(tmp_path, "cfg.json", json.dumps({"include_summary": False}))
    data = write(tmp_path, "data.csv", CSV)
    out = generate(cfg, data)
    assert "rows)" not in out
