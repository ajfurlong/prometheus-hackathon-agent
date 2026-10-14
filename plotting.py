"""Plot TableData as PNG with explicit units, missing-value gaps and isolated figures."""

import math
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from table_data import TableData, numeric

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]


def _auto_style(column: str, numeric_x: bool) -> str:
    """Choose a chart style from time-axis metadata; never select columns or infer y units."""
    temporal = re.search(
        r"\b(time|date|timestamp|year|month|day|night)\b|[\[(](s|ms|min|h|hr|sec|years)[\])]",
        column,
        re.I,
    )
    if temporal and not re.search(r"\bage\b", column, re.I):
        return "line"
    return "scatter" if numeric_x else "bar"


def _draw(axis, xs: list, values: list, kind: str, label: str, index: int, count: int) -> None:
    """Draw one series; NaNs retain gaps rather than inventing missing observations."""
    values = [math.nan if v is None else v for v in values]
    style = {"label": label, "color": COLORS[index % len(COLORS)]}
    if kind == "line":
        marker = "o" if len(xs) <= 30 else None
        axis.plot(xs, values, linewidth=2, marker=marker, markersize=4, **style)
    elif kind == "scatter":
        axis.scatter(xs, values, s=35, alpha=0.85, **style)
    else:
        width = 0.8 / count
        positions = [i - 0.4 + width * (index + 0.5) for i in range(len(xs))]
        axis.bar(positions, values, width=width, **style)
        axis.set_xticks(range(len(xs)), [str(x) for x in xs])


def render_plot(
    table: TableData,
    x_column: str,
    y_columns: list[str],
    output: Path,
    chart_type: str = "auto",
    title: str | None = None,
) -> dict:
    """Write a PNG and return plot metadata; use separate panels for incompatible y units."""
    if chart_type not in {"auto", "line", "scatter", "bar"}:
        raise ValueError("Chart type must be auto, line, scatter, or bar.")
    rows, xs, numeric_x = table.plot_rows(x_column, y_columns)
    kind = _auto_style(x_column, numeric_x) if chart_type == "auto" else chart_type
    units = [re.search(r"[\[(]([^\])]+)[\])]", y) for y in y_columns]
    separate = len({unit.group(1) if unit else "" for unit in units}) > 1
    panels = len(y_columns) if separate else 1
    figure = Figure(figsize=(10, max(5.5, 3.2 * panels)), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(panels, 1, squeeze=False).ravel()
    figure.suptitle(
        textwrap.fill((title or table.caption)[:240], 90), fontsize=12, fontweight="bold"
    )
    missing = {}
    for index, y in enumerate(y_columns):
        axis = axes[index] if separate else axes[0]
        values = [numeric(row[table.columns.index(y)]) for row in rows]
        if all(value is None for value in values):
            raise ValueError(f"Column {y!r} has no numeric pairs with {x_column!r}.")
        missing[y] = sum(value is None for value in values)
        position, count = (0, 1) if separate else (index, len(y_columns))
        _draw(axis, xs, values, kind, y, position, count)
        label = (
            y
            if separate or len(y_columns) == 1
            else f"Value ({units[0].group(1)})"
            if units[0]
            else "Value"
        )
        axis.set(xlabel=x_column, ylabel=label)
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        if len(xs) > 8 and (not numeric_x or kind == "bar"):
            axis.tick_params(axis="x", rotation=40, labelsize=9)
        if numeric_x and kind != "bar" and all(float(x).is_integer() for x in xs):
            axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    if len(y_columns) > 1 and not separate:
        axes[0].legend(frameon=False, loc="best")
    if any(missing.values()):
        figure.supxlabel("Missing values are omitted; lines break at gaps.", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, format="png", dpi=150)
    return {
        "chart_type": kind,
        "rows": len(rows),
        "missing_values": missing,
        "x_rows_omitted": len(table.rows) - len(rows),
    }
