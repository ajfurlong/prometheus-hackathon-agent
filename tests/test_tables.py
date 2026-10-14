import pytest

from markdown_parser import parse_markdown, split_cells
from table_data import TableData, numeric, parse_csv


def test_almanac_tables_preserve_exact_values():
    from pathlib import Path

    tables = parse_markdown((Path(__file__).parent / "fixtures/hollowmere_almanac.md").read_text())
    assert [len(t.rows) for t in tables] == [15, 12, 8]
    assert tables[0].columns == ["Year", "Thistledown", "Mossbury", "Pebblewick", "Total"]
    assert tables[0].rows[0] == ["2010", "416", "382", "172", "974"]
    assert tables[0].rows[-1] == ["2024", "475", "391", "418", "1300"]
    assert tables[2].rows[0][-1] == "toasted marshmallows"
    assert "Favourite snack" not in tables[2].numeric_columns()
    assert parse_csv(tables[0].to_csv()).rows == tables[0].rows


def test_multiline_caption_and_trailing_prose():
    text = "**Table 9. Thermal log of the\nreactor core.** Extra description.\n\n| t [s] | T [K] |\n| ---: | :--- |\n| 0 | 1,234 |\n| 1 | — |"
    table = parse_markdown(text)[0]
    assert table.caption == "Table 9. Thermal log of the reactor core."
    assert table.rows == [["0", "1,234"], ["1", "—"]]
    assert table.numeric_columns() == ["t [s]", "T [K]"]


def test_fenced_examples_are_not_document_tables():
    text = "```markdown\n| a | b |\n| --- | --- |\n| 1 | 2 |\n```\n\n**Real**\n| x | y |\n| --- | --- |\n| 3 | 4 |"
    assert [table.caption for table in parse_markdown(text)] == ["Real"]


def test_escaped_pipes_and_missing_cells():
    assert split_cells(r"| a\|b | 1 |") == ["a|b", "1"]
    assert split_cells("| empty | |") == ["empty", ""]
    assert split_cells(r"a\|b | 2") == ["a|b", "2"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1,234", 1234),
        ("−4.2", -4.2),
        ("(5)", -5),
        ("2.1e3", 2100),
        ("10%", 10),
        ("1\u202f234", 1234),
        ("—", None),
        ("N/A", None),
        ("12,34", None),
        ("dragon", None),
        ("inf", None),
        ("1e999", None),
    ],
)
def test_numeric_conversion_is_explicit(value, expected):
    assert numeric(value) == expected


def test_csv_quotes_bom_missing_values_and_unicode():
    table = parse_csv('\ufeffname,"mass (kg)",note\n"a,b","1,234","say ""hi"""\nother,,unknown\n')
    assert table.columns == ["name", "mass (kg)", "note"]
    assert table.rows[0][0] == "a,b"
    assert table.rows[1][1] == ""
    assert table.numeric_columns() == ["mass (kg)"]
    assert parse_csv(table.to_csv()).rows == table.rows


def test_tsv_and_semicolon_inputs():
    assert parse_csv("x\ty\n1\t2").columns == ["x", "y"]
    assert parse_csv("x;y\n1;2").rows == [["1", "2"]]


@pytest.mark.parametrize("text", ["", "x,x\n1,2", "x,y\n1,2,3"])
def test_invalid_csv_has_clear_error(text):
    with pytest.raises(ValueError):
        parse_csv(text)


def test_malformed_markdown_rows_are_not_silently_truncated():
    with pytest.raises(ValueError, match="expected 2 cells"):
        parse_markdown("| x | y |\n| --- | --- |\n| 1 | 2 | 3 |")


def test_invalid_inline_table_payload():
    with pytest.raises(ValueError):
        TableData.from_dict({"columns": ["x"], "rows": [[{"unexpected": 1}]]})
