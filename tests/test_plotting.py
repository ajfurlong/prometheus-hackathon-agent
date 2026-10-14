import pytest

from plotting import render_plot
from tables import Table


def test_png_and_missing_value_gaps(tmp_path):
    table = Table(
        "Population", ["Year", "Residents"], [["2021", "1,200"], ["2022", "—"], ["2023", "1400"]]
    )
    path = tmp_path / "plot.png"
    result = render_plot(table, "Year", ["Residents"], path)
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert result["chart_type"] == "line"
    assert result["missing_values"] == {"Residents": 1}


def test_categorical_data_and_mixed_units(tmp_path):
    table = Table(
        "Measurements", ["Name", "Mass (kg)", "Speed (m/s)"], [["A", "1", "2"], ["B", "2", "3"]]
    )
    assert (
        render_plot(table, "Name", ["Mass (kg)", "Speed (m/s)"], tmp_path / "plot.png")[
            "chart_type"
        ]
        == "bar"
    )


def test_numeric_comparison_is_scatter(tmp_path):
    table = Table("Dragons", ["Age (years)", "Wingspan (m)"], [["6", "3.2"], ["87", "10.7"]])
    assert (
        render_plot(table, "Wingspan (m)", ["Age (years)"], tmp_path / "scatter.png")["chart_type"]
        == "scatter"
    )
    assert (
        render_plot(table, "Age (years)", ["Wingspan (m)"], tmp_path / "age.png")["chart_type"]
        == "scatter"
    )


def test_caption_does_not_invent_population_units(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    labels = []
    savefig = Figure.savefig

    def capture_labels(figure, *args, **kwargs):
        labels.extend(axis.get_ylabel() for axis in figure.axes)
        return savefig(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture_labels)
    table = Table(
        "Bacterial population growth rates",
        ["Day", "Culture A", "Culture B"],
        [["1", "5%", "10%"], ["2", "7%", "12%"]],
    )
    path = tmp_path / "growth.png"
    render_plot(table, "Day", ["Culture A", "Culture B"], path)
    assert labels == ["Value"]
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("ys", [["Snack"], ["Year"], ["unknown"]])
def test_nonnumeric_or_invalid_series_are_rejected(tmp_path, ys):
    table = Table("Data", ["Year", "Population", "Snack"], [["2020", "10", "cake"]])
    with pytest.raises(ValueError):
        render_plot(table, "Year", ys, tmp_path / "plot.png")
