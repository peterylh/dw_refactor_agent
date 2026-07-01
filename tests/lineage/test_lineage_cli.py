import json

import pytest

import config
from lineage.lineage_cli import main
from tests.lineage.test_lineage_query import (
    _demo_view,
    configure_demo_project_layers,
)


@pytest.fixture(autouse=True)
def demo_project_layers(monkeypatch, tmp_path):
    configure_demo_project_layers(monkeypatch, tmp_path)
    yield
    config._model_metadata_cache.clear()


def _write_demo_lineage(tmp_path):
    path = tmp_path / "lineage_data_demo.json"
    path.write_text(
        json.dumps(_demo_view().snapshot.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_demo_project_lineage(tmp_path, monkeypatch):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "lineage"
    lineage_dir.mkdir(parents=True)
    path = lineage_dir / "lineage_data.json"
    path.write_text(
        json.dumps(_demo_view().snapshot.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )
    return path


def test_stats_reads_project_lineage_artifact_by_default(
    tmp_path, monkeypatch, capsys
):
    _write_demo_project_lineage(tmp_path, monkeypatch)

    exit_code = main(["stats", "--project", "demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Lineage Stats: demo" in captured.out
    assert "Tables: 6" in captured.out


def test_table_prints_table_lineage(tmp_path, capsys):
    _write_demo_lineage(tmp_path)

    exit_code = main(
        [
            "table",
            "--project",
            "demo",
            "--lineage-dir",
            str(tmp_path),
            "--table",
            "ads_sales_dashboard",
            "--direction",
            "upstream",
            "--depth",
            "2",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Lineage: demo / ads_sales_dashboard" in captured.out
    assert "Tables: 4   Edges: 3   Jobs: 2" in captured.out


def test_show_is_not_a_supported_command(tmp_path):
    _write_demo_lineage(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "show",
                "--project",
                "demo",
                "--lineage-dir",
                str(tmp_path),
                "--table",
                "ads_sales_dashboard",
            ]
        )

    assert exc.value.code == 2


def test_column_requires_column_argument(tmp_path):
    _write_demo_lineage(tmp_path)

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "column",
                "--project",
                "demo",
                "--lineage-dir",
                str(tmp_path),
                "--table",
                "dws_product_sales_daily",
            ]
        )

    assert exc.value.code == 2


def test_column_prints_column_lineage(tmp_path, capsys):
    _write_demo_lineage(tmp_path)

    exit_code = main(
        [
            "column",
            "--project",
            "demo",
            "--lineage-dir",
            str(tmp_path),
            "--table",
            "dws_product_sales_daily",
            "--column",
            "sales_amount",
            "--depth",
            "2",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert (
        "Column Lineage: demo / dws_product_sales_daily.sales_amount"
        in captured.out
    )
    assert "ods_order.sale_amount" in captured.out


def test_column_verbose_prints_condition_lineage(tmp_path, capsys):
    _write_demo_lineage(tmp_path)

    exit_code = main(
        [
            "column",
            "--project",
            "demo",
            "--lineage-dir",
            str(tmp_path),
            "--table",
            "dws_product_sales_daily",
            "--column",
            "sales_amount",
            "--depth",
            "2",
            "--verbose",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "conditions:" in captured.out
    assert (
        "FILTER dwd_order_detail.order_date: order_date = @etl_date"
        in captured.out
    )


def test_stats_prints_project_counts(tmp_path, capsys):
    _write_demo_lineage(tmp_path)

    exit_code = main(
        [
            "stats",
            "--project",
            "demo",
            "--lineage-dir",
            str(tmp_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Lineage Stats: demo" in captured.out
    assert "Tables: 6" in captured.out
    assert "Layers: ADS=2, DWD=2, DWS=1, ODS=1" in captured.out


def test_export_html_writes_selected_local_subgraph(tmp_path, capsys):
    _write_demo_lineage(tmp_path)
    output = tmp_path / "local_lineage.html"

    exit_code = main(
        [
            "export-html",
            "--project",
            "demo",
            "--lineage-dir",
            str(tmp_path),
            "--table",
            "ads_sales_dashboard",
            "--direction",
            "upstream",
            "--depth",
            "1",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    html = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert str(output) in captured.out
    assert "ads_sales_dashboard" in html
    assert "dws_product_sales_daily" in html
    assert "dwd_order_detail" not in html
    assert "ads_unrelated" not in html
