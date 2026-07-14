import json

import pytest

import dw_refactor_agent.config as config
from dw_refactor_agent.lineage.lineage_cli import main
from tests.lineage.test_lineage_query import (
    _demo_view,
    configure_demo_project_layers,
)


def _valid_lineage_v2():
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "source",
                "full_name": "internal.demo_dm.source",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
            {
                "name": "output",
                "full_name": "internal.demo_dm.output",
                "dataset_type": "managed",
                "columns": [{"name": "id", "type": "BIGINT"}],
            },
        ],
        "jobs": [
            {
                "name": "build_output",
                "source_file": "build_output.sql",
                "inputs": ["internal.demo_dm.source"],
                "outputs": ["internal.demo_dm.output"],
            }
        ],
        "edges": [
            {
                "source": {"type": "column", "id": "source.id"},
                "target": {"type": "column", "id": "output.id"},
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "id",
                "job": "build_output",
            }
        ],
        "diagnostics": [],
    }


def _valid_job_dag_v2():
    return {
        "format_version": 2,
        "jobs": ["build_output"],
        "data_dependencies": [],
        "deps": {"build_output": []},
        "rev": {"build_output": []},
    }


@pytest.fixture(autouse=True)
def demo_project_layers(monkeypatch, tmp_path):
    configure_demo_project_layers(monkeypatch, tmp_path)
    yield
    config.clear_model_metadata_cache()


def _write_demo_lineage(tmp_path):
    path = tmp_path / "lineage_data_demo.json"
    path.write_text(
        json.dumps(_demo_view().snapshot.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _write_demo_project_lineage(tmp_path, monkeypatch):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    path = lineage_dir / "lineage_data.json"
    path.write_text(
        json.dumps(_demo_view().snapshot.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )
    return path


def _write_v2_project_artifacts(
    tmp_path, monkeypatch, *, lineage=None, dag=None
):
    project_dir = tmp_path / "demo_project"
    lineage_dir = project_dir / "artifacts" / "lineage"
    lineage_dir.mkdir(parents=True)
    lineage_path = lineage_dir / "lineage_data.json"
    lineage_path.write_text(
        json.dumps(lineage or _valid_lineage_v2(), ensure_ascii=False),
        encoding="utf-8",
    )
    dag_path = lineage_dir / "job_dag.json"
    dag_path.write_text(
        json.dumps(dag or _valid_job_dag_v2(), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )
    return lineage_path, dag_path


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


@pytest.mark.parametrize(
    ("command", "table_name"),
    [
        ("show", "ads_sales_dashboard"),
        ("column", "dws_product_sales_daily"),
    ],
    ids=("unsupported-command", "missing-column-argument"),
)
def test_invalid_command_line_arguments_exit_with_usage_error(
    tmp_path, command, table_name
):
    with pytest.raises(SystemExit) as exc:
        main(
            [
                command,
                "--project",
                "demo",
                "--lineage-dir",
                str(tmp_path),
                "--table",
                table_name,
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


def test_validate_accepts_strict_lineage_and_job_dag_v2(
    tmp_path, monkeypatch, capsys
):
    lineage_path, dag_path = _write_v2_project_artifacts(tmp_path, monkeypatch)

    exit_code = main(["validate", "--project", "demo"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert str(lineage_path) in captured.out
    assert str(dag_path) in captured.out
    assert "lineage v2 valid" in captured.out
    assert "job DAG v2 valid" in captured.out


def test_validate_rejects_forbidden_v2_edge_source_file(
    tmp_path, monkeypatch, capsys
):
    lineage = _valid_lineage_v2()
    lineage["edges"][0]["source_file"] = "build_output.sql"
    _write_v2_project_artifacts(tmp_path, monkeypatch, lineage=lineage)

    exit_code = main(["validate", "--project", "demo"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "source_file" in captured.err


def test_validate_strictly_rejects_invalid_job_dag_v2(
    tmp_path, monkeypatch, capsys
):
    dag = _valid_job_dag_v2()
    dag["edges"] = []
    _write_v2_project_artifacts(tmp_path, monkeypatch, dag=dag)

    exit_code = main(["validate", "--project", "demo"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "edges" in captured.err
