"""Deterministic, lossless readers for captioned GFM tables and CSV/TSV files."""

from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass

MISSING = {"", "-", "–", "—", "na", "n/a", "nan", "null", "none", "...", "…"}
NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
GROUPED = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d*)?(?:[eE][+-]?\d+)?$")
SEPARATOR = re.compile(r"^:?-{3,}:?$")


@dataclass
class Table:
    caption: str
    columns: list[str]
    rows: list[list[str]]
    source_line: int = 0

    def __post_init__(self) -> None:
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
        return {
            "caption": self.caption,
            "columns": self.columns,
            "rows": self.rows,
            "source_line": self.source_line,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Table:
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
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return output.getvalue()

    def numeric_columns(self) -> list[str]:
        result = []
        for index, column in enumerate(self.columns):
            cells = [row[index] for row in self.rows]
            if any(numeric(cell) is not None for cell in cells) and all(
                is_missing(cell) or numeric(cell) is not None for cell in cells
            ):
                result.append(column)
        return result


def is_missing(value: str) -> bool:
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


def split_cells(line: str) -> list[str]:
    """Split GFM pipes, respecting escaped pipes and escaped backslashes."""
    line = line.strip()
    cells, cell = [], []
    index = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line) and line[index + 1] in "|\\":
            cell.append(line[index + 1])
            index += 2
            continue
        if char == "|":
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
        index += 1
    cells.append("".join(cell).strip())
    if line.startswith("|"):
        cells.pop(0)
    # An escaped final pipe is part of the last cell, not a table border.
    if line.endswith("|") and cells[-1] == "":
        cells.pop()
    return cells


def parse_markdown(text: str) -> list[Table]:
    lines = text.lstrip("\ufeff").splitlines()
    tables = []
    fence = None
    index = 0
    while index < len(lines) - 1:
        line = lines[index]
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = (run[0], len(run))
            elif run[0] == fence[0] and len(run) >= fence[1] and not line[marker.end() :].strip():
                fence = None
            index += 1
            continue
        if fence or "|" not in line:
            index += 1
            continue
        headers = split_cells(line)
        separators = split_cells(lines[index + 1])
        if len(headers) != len(separators) or not all(
            SEPARATOR.fullmatch(cell.replace(" ", "")) for cell in separators
        ):
            index += 1
            continue
        # Captions can wrap across lines; only the immediately preceding paragraph counts.
        end = index - 1
        while end >= 0 and not lines[end].strip():
            end -= 1
        start = end
        while start >= 0 and lines[start].strip():
            start -= 1
        paragraph = " ".join(lines[start + 1 : end + 1])
        caption = re.search(r"\*\*(.*?)\*\*", paragraph)
        title = caption.group(1).strip() if caption else f"Table {len(tables) + 1}"
        source_line = index + 1
        index += 2
        rows = []
        while index < len(lines) and lines[index].strip() and "|" in lines[index]:
            rows.append(split_cells(lines[index]))
            index += 1
        tables.append(Table(title, headers, rows, source_line))
    return tables


def parse_csv(text: str, caption: str = "CSV data", delimiter: str | None = None) -> Table:
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
    return Table(caption, [cell.strip() for cell in rows[0]], rows[1:])
