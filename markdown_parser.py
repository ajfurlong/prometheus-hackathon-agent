"""Deterministically parse captioned GFM Markdown into TableData objects."""

import re

from table_data import TableData

SEPARATOR = re.compile(r"^:?-{3,}:?$")


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


def parse_markdown(text: str) -> list[TableData]:
    """Read captioned GFM tables, ignoring fenced examples and retaining source lines."""
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
        tables.append(TableData(title, headers, rows, source_line))
    return tables
