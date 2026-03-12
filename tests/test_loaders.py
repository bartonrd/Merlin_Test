"""Tests for the document loaders."""


def test_load_csv_basic(tmp_path):
    """CSV rows should be converted to comma-separated text lines."""
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")

    from app.ingestion.loaders import load_csv

    result = load_csv(csv_file)
    assert "name, value" in result
    assert "alpha, 1" in result
    assert "beta, 2" in result


def test_load_csv_via_load_text(tmp_path):
    """load_text should dispatch to load_csv for .csv files."""
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("col1,col2\nfoo,bar\n", encoding="utf-8")

    from app.ingestion.loaders import load_text

    result = load_text(csv_file)
    assert "col1, col2" in result
    assert "foo, bar" in result


def test_load_txt_via_load_text(tmp_path):
    """load_text should dispatch to load_txt for .txt files."""
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello world", encoding="utf-8")

    from app.ingestion.loaders import load_text

    result = load_text(txt_file)
    assert result == "hello world"



