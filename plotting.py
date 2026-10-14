"""Render honest, readable PNG plots without a GUI or global pyplot state."""

from __future__ import annotations

import math
import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402

from matching import column_tokens
from tables import Table, is_missing, numeric

COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9"]


def render_plot(
    table: Table,
    x_column: str,
    y_columns: list[str],
    output: Path,
    chart_type: str = "auto",
    title: str | None = None,
) -> dict:
    if x_column not in table.columns or not y_columns:
        raise ValueError("Choose an existing x column and at least one y column.")
    if any(y not in table.numeric_columns() or y == x_column for y in y_columns):
        raise ValueError("Y columns must contain numbers and must differ from the x column.")
    if chart_type not in {"auto", "line", "scatter", "bar"}:
        raise ValueError("Chart type must be auto, line, scatter, or bar.")
    xi = table.columns.index(x_column)
    usable = [row for row in table.rows if not is_missing(row[xi])]
    if not usable:
        raise ValueError("The x column has no usable values.")
    numeric_x = all(numeric(row[xi]) is not None for row in usable)
    if numeric_x:
        usable = sorted(usable, key=lambda row: numeric(row[xi]))
    concepts = column_tokens(x_column)
    temporal = ("time" in concepts or "date" in concepts) and "age" not in concepts
    kind = (
        chart_type
        if chart_type != "auto"
        else "line"
        if temporal
        else "scatter"
        if numeric_x
        else "bar"
    )
    xs = [numeric(row[xi]) if numeric_x else row[xi] for row in usable]
    units = [re.search(r"[\[(]([^\])]+)[\])]", y) for y in y_columns]
    different_units = len({unit.group(1) if unit else "" for unit in units}) > 1
    panels = len(y_columns) if different_units else 1
    figure = Figure(figsize=(10, max(5.5, 3.2 * panels)), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    axes = [figure.add_subplot(panels, 1, index + 1) for index in range(panels)]
    figure.suptitle(
        textwrap.fill((title or table.caption)[:240], 90), fontsize=12, fontweight="bold"
    )
    missing = {}
    for series, y in enumerate(y_columns):
        axis = axes[series] if different_units else axes[0]
        yi = table.columns.index(y)
        values = [numeric(row[yi]) for row in usable]
        if all(value is None for value in values):
            raise ValueError(f"Column {y!r} has no numeric pairs with {x_column!r}.")
        missing[y] = sum(value is None for value in values)
        ys = [math.nan if value is None else value for value in values]
        color = COLORS[series % len(COLORS)]
        if kind == "line":
            axis.plot(
                xs,
                ys,
                label=y,
                color=color,
                linewidth=2,
                marker="o" if len(xs) <= 30 else None,
                markersize=4,
            )
        elif kind == "scatter":
            axis.scatter(xs, ys, label=y, color=color, s=35, alpha=0.85)
        else:
            count = 1 if different_units else len(y_columns)
            offset = 0 if different_units else series
            width = 0.8 / count
            positions = [i - 0.4 + width * (offset + 0.5) for i in range(len(xs))]
            axis.bar(positions, ys, width=width, label=y, color=color)
            axis.set_xticks(range(len(xs)), [str(x) for x in xs])
        axis.set_xlabel(x_column)
        if different_units or len(y_columns) == 1:
            axis.set_ylabel(y)
        elif units[0]:
            axis.set_ylabel(f"Value ({units[0].group(1)})")
        else:
            axis.set_ylabel("Value")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        if len(xs) > 8 and (not numeric_x or kind == "bar"):
            axis.tick_params(axis="x", rotation=40, labelsize=9)
        if numeric_x and all(float(x).is_integer() for x in xs) and kind != "bar":
            axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    if len(y_columns) > 1 and not different_units:
        axes[0].legend(frameon=False, loc="best")
    if any(missing.values()):
        figure.supxlabel("Missing values are omitted; lines break at gaps.", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, format="png", dpi=150)
    return {
        "chart_type": kind,
        "rows": len(usable),
        "missing_values": missing,
        "x_rows_omitted": len(table.rows) - len(usable),
    }
