"""Validated rectangular table data, CSV serialization and numeric conversion."""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass

MISSING = {"", "-", "–", "—", "na", "n/a", "nan", "null", "none", "...", "…"}
NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
GROUPED = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?(?:[eE][+-]?\d+)?$")


@dataclass
class TableData:
    """Lossless string cells with a caption, unique headers and rectangular rows."""

    caption: str
    columns: list[str]
    rows: list[list[str]]
    source_line: int = 0

    def __post_init__(self) -> None:
        """Reject ambiguous headers and inconsistent row widths."""
        if not self.columns or any(not column.strip() for column in self.columns):
            raise ValueError("Table headers must be nonempty.")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Duplicate column names are ambiguous; rename them in the source.")
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"Table at line {self.source_line}: expected {len(self.columns)} cells, "
                    f"received {len(row)}."
                )

    def to_dict(self) -> dict:
        """Return the serializable table contract used by artifact metadata and tests."""
        return {
            "caption": self.caption,
            "columns": self.columns,
            "rows": self.rows,
            "source_line": self.source_line,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> TableData:
        """Validate a table JSON object and preserve scalar cells as strings."""
        columns, rows = payload.get("columns"), payload.get("rows")
        if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
            raise ValueError("A table must have a list of column names.")
        if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
            raise ValueError("A table must have a list of rows.")
        if any(isinstance(cell, (list, dict)) for row in rows for cell in row):
            raise ValueError("Table cells must be scalar values.")
        return cls(
            str(payload.get("caption") or "Tabular data"),
            columns,
            [["" if cell is None else str(cell) for cell in row] for row in rows],
        )

    def to_csv(self) -> str:
        """Serialize exact cell values with standard CSV quoting and LF endings."""
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return output.getvalue()

    def numeric_columns(self) -> list[str]:
        """List columns containing numbers or missing markers, with at least one number."""
        result = []
        for index, column in enumerate(self.columns):
            cells = [row[index] for row in self.rows]
            if any(numeric(cell) is not None for cell in cells) and all(
                is_missing(cell) or numeric(cell) is not None for cell in cells
            ):
                result.append(column)
        return result

    def plot_rows(self, x: str, ys: list[str]) -> tuple[list, list, bool]:
        """Validate columns, omit missing x cells and sort numeric x without changing source rows."""
        if x not in self.columns or not ys:
            raise ValueError("Choose an existing x column and at least one y column.")
        if any(y not in self.numeric_columns() or y == x for y in ys):
            raise ValueError("Y columns must contain numbers and must differ from the x column.")
        xi = self.columns.index(x)
        rows = [row for row in self.rows if not is_missing(row[xi])]
        if not rows:
            raise ValueError("The x column has no usable values.")
        numeric_x = all(numeric(row[xi]) is not None for row in rows)
        if numeric_x:
            rows = sorted(rows, key=lambda row: numeric(row[xi]))
        return rows, [numeric(row[xi]) if numeric_x else row[xi] for row in rows], numeric_x


def is_missing(value: str) -> bool:
    """Recognize documented empty or missing-value markers without changing cells."""
    return str(value).strip().casefold() in MISSING


def numeric(value: str) -> float | None:
    """Recognize numbers without changing source cells or treating text as numbers."""
    text = str(value).strip().replace("−", "-")
    if is_missing(text):
        return None
    text = re.sub(r"[\u00a0\u202f\u2009]", "", text)
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    if text.endswith("%"):
        text = text[:-1].strip()
    if GROUPED.fullmatch(text):
        text = text.replace(",", "")
    if not NUMBER.fullmatch(text):
        return None
    value = float(text)
    value = -value if negative else value
    return value if math.isfinite(value) else None


def parse_csv(text: str, caption: str = "CSV data", delimiter: str | None = None) -> TableData:
    """Read UTF-8 CSV/TSV text, sniffing comma, semicolon or tab delimiters."""
    text = text.lstrip("\ufeff")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error as exc:
        raise ValueError(f"Invalid CSV: {exc}") from exc
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("The CSV file is empty.")
    return TableData(caption, [cell.strip() for cell in rows[0]], rows[1:])
