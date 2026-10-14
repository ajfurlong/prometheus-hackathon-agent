from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from prometheus_api.llm_client import ToolCall

from matching import is_vague, match_column, match_table, select_axes, select_table
from table_data import TableData


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("time", None),
        ("temperature", None),
        ("t", "t [min]"),
        ("T", "T [K]"),
        ("missing", None),
    ],
)
def test_symbols_and_units_do_not_confuse_time_and_temperature(query, expected):
    assert match_column(["t [min]", "T [K]", "Pressure (Pa)"], query) == expected


def test_ambiguous_column_requires_selection():
    assert match_column(["Core temp [°C]", "Rind temp [°C]"], "temperature") is None
    assert (
        match_column(["Core temp [°C]", "Rind temp [°C]"], "core temperature") == "Core temp [°C]"
    )


def test_caption_paraphrase_and_no_match():
    tables = [
        TableData("Midsummer census population", ["Year"], [["1"]]),
        TableData("Wild mushroom harvest", ["Month"], [["May"]]),
    ]
    assert match_table(tables, "the residents table") is None
    assert match_table(tables, "the mushroom harvest") == 1
    assert match_table(tables, "submarine fuel consumption") is None
    assert is_vague("plot this")


async def test_llm_selection_is_bounded_to_actual_columns():
    table = TableData("Heating", ["t [s]", "T [K]"], [["0", "300"]])
    llm = SimpleNamespace(
        medium=AsyncMock(
            return_value=SimpleNamespace(
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="choose_plot_columns",
                        arguments={"matched": True, "x_column": "t [s]", "y_columns": ["T [K]"]},
                    )
                ]
            )
        )
    )
    assert await select_axes(llm, table, "temperature over time") == ("t [s]", ["T [K]"])
    options = llm.medium.call_args.kwargs["tools"][0].parameters["properties"]
    assert options["x_column"]["enum"] == ["", "t [s]", "T [K]"]
    assert "rows" not in llm.medium.call_args.args[0][1]["content"]


async def test_hallucinated_columns_and_table_indices_are_rejected():
    llm = SimpleNamespace(
        medium=AsyncMock(
            return_value=SimpleNamespace(
                tool_calls=[
                    ToolCall(
                        id="1",
                        name="choose_plot_columns",
                        arguments={"matched": True, "x_column": "imaginary", "y_columns": ["y"]},
                    )
                ]
            )
        )
    )
    table = TableData("Numbers", ["x", "y"], [["1", "2"]])
    assert await select_axes(llm, table, "numbers") is None
    llm.medium.return_value = SimpleNamespace(
        tool_calls=[ToolCall(id="2", name="choose_table", arguments={"table_index": 99})]
    )
    assert await select_table(llm, [table], "numbers") is None
