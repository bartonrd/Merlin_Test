"""Tests for the document loaders."""


def test_load_md_basic(tmp_path):
    """Markdown files should be returned as plain text with markup preserved."""
    md_file = tmp_path / "notes.md"
    md_file.write_text("# Heading\n\nSome **bold** text.\n", encoding="utf-8")

    from app.ingestion.loaders import load_md

    result = load_md(md_file)
    assert "# Heading" in result
    assert "**bold**" in result


def test_load_md_via_load_text(tmp_path):
    """load_text should dispatch to load_md for .md files."""
    md_file = tmp_path / "readme.md"
    md_file.write_text("# Title\n\nContent here.\n", encoding="utf-8")

    from app.ingestion.loaders import load_text

    result = load_text(md_file)
    assert "# Title" in result
    assert "Content here." in result


def test_load_md_uppercase_extension(tmp_path):
    """load_text should handle .MD (uppercase) extensions the same as .md."""
    md_file = tmp_path / "ReadMe.MD"
    md_file.write_text("# ReadMe\n\nDetails here.\n", encoding="utf-8")

    from app.ingestion.loaders import load_text

    result = load_text(md_file)
    assert "# ReadMe" in result
    assert "Details here." in result


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

