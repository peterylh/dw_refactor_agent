import importlib
import json

import pytest

import dw_refactor_agent.config as config


def _demo_snapshot():
    return {
        "tables": [
            {
                "name": "ods_order",
                "full_name": "shop_dm.ods_order",
                "columns": [
                    {
                        "name": "amount",
                        "type": "DECIMAL(12,2)",
                        "comment": "订单金额",
                    },
                ],
            },
            {
                "name": "dwd_order_detail",
                "full_name": "shop_dm.dwd_order_detail",
                "columns": [
                    {
                        "name": "amount",
                        "type": "DECIMAL(12,2)",
                        "comment": "订单金额",
                    },
                ],
            },
        ],
        "edges": [
            {
                "source": {"type": "column", "id": "ods_order.amount"},
                "target": {"type": "column", "id": "dwd_order_detail.amount"},
                "relation_type": "direct",
                "expression": "amount",
                "source_file": "dwd_order_detail.sql",
            },
            {
                "source": {"type": "column", "id": "ods_order.amount"},
                "target": {"type": "table", "id": "dwd_order_detail"},
                "relation_type": "filter",
                "expression": "amount > 0",
                "source_file": "dwd_order_detail.sql",
            },
        ],
    }


def _demo_v2_snapshot():
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "ods_order",
                "full_name": "internal.shop_dm.ods_order",
                "dataset_type": "managed",
                "columns": [{"name": "amount", "type": "DECIMAL(12,2)"}],
            },
            {
                "name": "process_order",
                "full_name": "internal.shop_dm.process_order",
                "dataset_type": "process",
                "columns": [{"name": "amount", "type": "DECIMAL(12,2)"}],
            },
        ],
        "jobs": [
            {
                "name": "prepare_orders",
                "source_file": "prepare_orders.sql",
                "inputs": ["internal.shop_dm.ods_order"],
                "outputs": ["internal.shop_dm.process_order"],
            }
        ],
        "edges": [
            {
                "source": {
                    "type": "column",
                    "id": "internal.shop_dm.ods_order.amount",
                },
                "target": {
                    "type": "column",
                    "id": "internal.shop_dm.process_order.amount",
                },
                "relation_type": "direct",
                "transformation_type": "passthrough",
                "expression": "amount",
                "job": "prepare_orders",
            },
            {
                "source": {
                    "type": "column",
                    "id": "internal.shop_dm.ods_order.amount",
                },
                "target": {
                    "type": "table",
                    "id": "internal.shop_dm.process_order",
                },
                "relation_type": "filter",
                "transformation_type": "condition",
                "expression": "amount > 0",
                "job": "PREPARE_ORDERS",
            },
        ],
        "diagnostics": [],
    }


def _production_shaped_v2_snapshot():
    source_table = "internal.shop_dm.source_events"
    target_table = "internal.shop_dm.target_metrics"
    source_columns = [f"source_{index:03d}" for index in range(310)]
    column_targets = [f"column_target_{index:03d}" for index in range(310)]
    expression_targets = [
        f"expression_target_{index:03d}" for index in range(34)
    ]
    literal_targets = [f"literal_target_{index:03d}" for index in range(14)]
    edges = [
        {
            "source": {
                "type": "column",
                "id": f"{source_table}.{source_column}",
            },
            "target": {
                "type": "column",
                "id": f"{target_table}.{target_column}",
            },
            "relation_type": "direct",
            "transformation_type": "passthrough",
            "expression": source_column,
            "job": "build_target_metrics",
        }
        for source_column, target_column in zip(source_columns, column_targets)
    ]
    edges.extend(
        {
            "source": {
                "type": "expression",
                "expression": f"CURRENT_DATE() + INTERVAL {index} DAY",
            },
            "target": {
                "type": "column",
                "id": f"{target_table}.{target_column}",
            },
            "relation_type": "direct",
            "transformation_type": "calculation",
            "expression": f"CURRENT_DATE() + INTERVAL {index} DAY",
            "job": "build_target_metrics",
        }
        for index, target_column in enumerate(expression_targets)
    )
    edges.extend(
        {
            "source": {"type": "literal", "value": index},
            "target": {
                "type": "column",
                "id": f"{target_table}.{target_column}",
            },
            "relation_type": "direct",
            "transformation_type": "constant",
            "expression": str(index),
            "job": "build_target_metrics",
        }
        for index, target_column in enumerate(literal_targets)
    )
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "source_events",
                "full_name": source_table,
                "dataset_type": "managed",
                "columns": [
                    {"name": column_name, "type": "BIGINT"}
                    for column_name in source_columns
                ],
            },
            {
                "name": "target_metrics",
                "full_name": target_table,
                "dataset_type": "managed",
                "columns": [
                    {"name": column_name, "type": "BIGINT"}
                    for column_name in [
                        *column_targets,
                        *expression_targets,
                        *literal_targets,
                    ]
                ],
            },
        ],
        "jobs": [
            {
                "name": "build_target_metrics",
                "source_file": "build_target_metrics.sql",
                "inputs": [source_table],
                "outputs": [target_table],
            }
        ],
        "edges": edges,
        "diagnostics": [],
    }


def test_parser_accepts_test_db_env():
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    args = module.build_parser().parse_args(
        ["--project", "shop", "--db-env", "test"]
    )

    assert args.db_env == "test"


def test_default_lineage_file_ignores_old_tool_directory_file(
    monkeypatch, tmp_path
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    project_dir = tmp_path / "demo_project"
    (project_dir / "artifacts" / "lineage").mkdir(parents=True)
    old_lineage_dir = tmp_path / "lineage"
    old_lineage_dir.mkdir()
    (old_lineage_dir / "lineage_data_demo.json").write_text(
        "{}",
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "LINEAGE_DIR", old_lineage_dir)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "demo_project",
        },
    )

    assert module._lineage_file("demo", None) == (
        project_dir / "artifacts" / "lineage" / "lineage_data.json"
    )


def test_open_connection_uses_selected_db_env(monkeypatch):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(module.pymysql, "connect", fake_connect)

    conn = module._open_connection("shop_lineage", db_env="test")

    assert conn is calls[0] or conn is not None
    assert calls == [
        {
            "host": "172.16.0.90",
            "port": 9034,
            "user": "root",
            "database": "shop_lineage",
            "charset": "utf8mb4",
        }
    ]


def test_build_import_rows_normalizes_snapshot_for_database(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "dwd_order_detail.sql").write_text(
        "INSERT INTO dwd_order_detail SELECT amount FROM ods_order;",
        encoding="utf-8",
    )

    rows = module.build_import_rows(
        _demo_snapshot(),
        tasks_dir=tasks_dir,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.datasource_rows == [
        (1, 42, "shop", "shop_dm", "doris", "127.0.0.1:9030"),
    ]
    assert rows.table_rows == [
        (1, 42, 1, "ods_order", "shop_dm.ods_order", "managed", 0, "[]"),
        (
            2,
            42,
            1,
            "dwd_order_detail",
            "shop_dm.dwd_order_detail",
            "managed",
            0,
            "[]",
        ),
    ]
    assert rows.column_rows == [
        (1, 42, 1, "amount", "DECIMAL(12,2)", "订单金额", 0),
        (2, 42, 2, "amount", "DECIMAL(12,2)", "订单金额", 0),
    ]
    assert rows.job_rows == [
        (
            1,
            42,
            "dwd_order_detail",
            "dwd_order_detail.sql",
            "SQL",
            "INSERT INTO dwd_order_detail SELECT amount FROM ods_order;",
        )
    ]
    assert rows.column_lineage_rows == [
        (
            1,
            42,
            1,
            1,
            2,
            2,
            1,
            "DIRECT",
            "",
            "amount",
        )
    ]
    assert rows.indirect_lineage_rows == [
        (1, 42, 1, 1, 2, 1, "FILTER", "amount > 0"),
    ]
    assert rows.table_lineage_rows == [
        (1, 42, 1, 2, 1, "DIRECT"),
        (2, 42, 1, 2, 1, "FILTER"),
    ]
    assert rows.skipped_edges == []


def test_build_import_rows_uses_explicit_v2_jobs_and_job_dataset_io(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "prepare_orders.sql").write_text(
        "CREATE TABLE process_order AS SELECT amount FROM ods_order;",
        encoding="utf-8",
    )

    rows = module.build_import_rows(
        _demo_v2_snapshot(),
        tasks_dir=tasks_dir,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.table_rows == [
        (
            1,
            42,
            1,
            "ods_order",
            "internal.shop_dm.ods_order",
            "managed",
            0,
            "[]",
        ),
        (
            2,
            42,
            1,
            "process_order",
            "internal.shop_dm.process_order",
            "process",
            0,
            "[]",
        ),
    ]
    assert rows.job_rows == [
        (
            1,
            42,
            "prepare_orders",
            "prepare_orders.sql",
            "SQL",
            "CREATE TABLE process_order AS SELECT amount FROM ods_order;",
        )
    ]
    assert rows.job_dataset_rows == [
        (42, 1, 1, "INPUT"),
        (42, 1, 2, "OUTPUT"),
    ]
    assert rows.column_lineage_rows == [
        (
            1,
            42,
            1,
            1,
            2,
            2,
            1,
            "DIRECT",
            "passthrough",
            "amount",
        )
    ]
    assert rows.indirect_lineage_rows == [
        (1, 42, 1, 1, 2, 1, "FILTER", "amount > 0")
    ]
    assert rows.skipped_edges == []


def test_build_import_rows_matches_equivalent_v2_table_qualifications(
    tmp_path,
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["jobs"][0]["inputs"] = ["shop_dm.ods_order"]
    data["jobs"][0]["outputs"] = ["shop_dm.process_order"]
    for edge in data["edges"]:
        edge["source"]["id"] = edge["source"]["id"].replace("internal.", "")
        edge["target"]["id"] = edge["target"]["id"].replace("internal.", "")

    rows = module.build_import_rows(
        data,
        tasks_dir=tmp_path,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.job_dataset_rows == [
        (42, 1, 1, "INPUT"),
        (42, 1, 2, "OUTPUT"),
    ]
    assert len(rows.column_lineage_rows) == 1
    assert len(rows.indirect_lineage_rows) == 1
    assert rows.skipped_edges == []


@pytest.mark.parametrize(
    ("source_ref", "source_payload"),
    [
        (
            {"type": "literal", "value": "ALL"},
            '{"type":"literal","value":"ALL"}',
        ),
        (
            {"type": "literal", "value": 7},
            '{"type":"literal","value":7}',
        ),
        (
            {"type": "literal", "value": True},
            '{"type":"literal","value":true}',
        ),
        (
            {"type": "literal", "value": None},
            '{"type":"literal","value":null}',
        ),
        (
            {"type": "expression", "expression": "CURRENT_DATE()"},
            '{"type":"expression","expression":"CURRENT_DATE()"}',
        ),
    ],
    ids=(
        "string-literal",
        "number-literal",
        "boolean-literal",
        "null-literal",
        "expression",
    ),
)
def test_build_import_rows_persists_v2_non_column_direct_sources_losslessly(
    tmp_path, source_ref, source_payload
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][0]]
    data["edges"][0]["source"] = source_ref

    rows = module.build_import_rows(
        data,
        tasks_dir=tmp_path,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.column_lineage_rows == []
    assert rows.non_column_direct_lineage_rows == [
        (
            1,
            42,
            2,
            2,
            1,
            "DIRECT",
            "passthrough",
            "amount",
            source_ref["type"],
            source_payload,
        )
    ]
    assert rows.skipped_edges == []


def test_build_import_rows_accepts_hermetic_production_shaped_v2_sources(
    monkeypatch, tmp_path
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    monkeypatch.setattr(
        config,
        "lineage_data_path",
        lambda *_args, **_kwargs: pytest.fail(
            "hermetic importer test must not read generated artifacts"
        ),
    )

    rows = module.build_import_rows(
        _production_shaped_v2_snapshot(),
        tasks_dir=tmp_path,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert len(rows.column_lineage_rows) == 310
    assert len(rows.non_column_direct_lineage_rows) == 48
    source_types = [row[8] for row in rows.non_column_direct_lineage_rows]
    assert source_types.count("expression") == 34
    assert source_types.count("literal") == 14
    assert rows.skipped_edges == []


def test_import_rejects_unmapped_v2_non_column_target_before_connecting(
    monkeypatch, tmp_path
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][0]]
    data["edges"][0]["source"] = {"type": "literal", "value": "ALL"}
    data["edges"][0]["target"]["id"] = (
        "internal.shop_dm.process_order.missing_amount"
    )
    lineage_file = tmp_path / "lineage_data.json"
    lineage_file.write_text(json.dumps(data), encoding="utf-8")
    connection_opened = False

    def fail_if_connected(*_args, **_kwargs):
        nonlocal connection_opened
        connection_opened = True
        pytest.fail("database connection must not be opened")

    monkeypatch.setattr(module, "_open_connection", fail_if_connected)

    with pytest.raises(ValueError) as exc_info:
        module.import_lineage(
            project="shop",
            lineage_file=lineage_file,
            snapshot_id=42,
        )

    assert connection_opened is False
    message = str(exc_info.value)
    assert "missing_amount" in message
    assert "internal.shop_dm.process_order" in message


def test_build_import_rows_rejects_unsupported_v2_direct_shape(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][0]]
    data["edges"][0]["source"] = {
        "type": "expression",
        "expression": "CURRENT_DATE()",
    }
    data["edges"][0]["target"] = {
        "type": "table",
        "id": "internal.shop_dm.process_order",
    }

    with pytest.raises(ValueError) as exc_info:
        module.build_import_rows(
            data,
            tasks_dir=tmp_path,
            context=module.ImportContext(
                project="shop",
                snapshot_id=42,
                datasource_id=1,
                datasource_name="shop_dm",
                db_type="doris",
                host="127.0.0.1:9030",
            ),
        )

    message = str(exc_info.value)
    assert "DIRECT" in message
    assert "CURRENT_DATE()" in message
    assert "internal.shop_dm.process_order" in message


@pytest.mark.parametrize(
    ("literal_value", "expected_identity"),
    [(False, "false"), (0, "0"), (None, "null")],
    ids=("false", "zero", "null"),
)
def test_build_import_rows_preserves_falsy_literal_in_direct_shape_error(
    tmp_path, literal_value, expected_identity
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][0]]
    data["edges"][0]["source"] = {
        "type": "literal",
        "value": literal_value,
    }
    data["edges"][0]["target"] = {
        "type": "table",
        "id": "internal.shop_dm.process_order",
    }

    with pytest.raises(ValueError) as exc_info:
        module.build_import_rows(
            data,
            tasks_dir=tmp_path,
            context=module.ImportContext(
                project="shop",
                snapshot_id=42,
                datasource_id=1,
                datasource_name="shop_dm",
                db_type="doris",
                host="127.0.0.1:9030",
            ),
        )

    message = str(exc_info.value)
    assert f"source='{expected_identity}' (literal)" in message
    assert "internal.shop_dm.process_order" in message


def test_build_import_rows_rejects_unmapped_v2_direct_column_metadata(
    tmp_path,
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][0]]
    data["edges"][0]["source"]["id"] = (
        "internal.shop_dm.ods_order.missing_amount"
    )

    with pytest.raises(ValueError) as exc_info:
        module.build_import_rows(
            data,
            tasks_dir=tmp_path,
            context=module.ImportContext(
                project="shop",
                snapshot_id=42,
                datasource_id=1,
                datasource_name="shop_dm",
                db_type="doris",
                host="127.0.0.1:9030",
            ),
        )

    message = str(exc_info.value)
    assert "missing_amount" in message
    assert "internal.shop_dm.ods_order" in message


@pytest.mark.parametrize(
    ("source_ref", "target_ref", "source_label", "target_label"),
    [
        (
            {"type": "literal", "value": "ALL"},
            {"type": "table", "id": "internal.shop_dm.process_order"},
            "ALL",
            "internal.shop_dm.process_order",
        ),
        (
            {
                "type": "column",
                "id": "internal.shop_dm.ods_order.amount",
            },
            {
                "type": "column",
                "id": "internal.shop_dm.process_order.amount",
            },
            "internal.shop_dm.ods_order.amount",
            "internal.shop_dm.process_order.amount",
        ),
    ],
    ids=("literal-to-table", "column-to-column"),
)
def test_build_import_rows_rejects_unrepresentable_v2_indirect_edges(
    tmp_path,
    source_ref,
    target_ref,
    source_label,
    target_label,
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][1]]
    data["edges"][0]["source"] = source_ref
    data["edges"][0]["target"] = target_ref

    with pytest.raises(ValueError) as exc_info:
        module.build_import_rows(
            data,
            tasks_dir=tmp_path,
            context=module.ImportContext(
                project="shop",
                snapshot_id=42,
                datasource_id=1,
                datasource_name="shop_dm",
                db_type="doris",
                host="127.0.0.1:9030",
            ),
        )

    message = str(exc_info.value)
    assert "FILTER" in message
    assert "PREPARE_ORDERS" in message
    assert source_label in message
    assert target_label in message


def test_build_import_rows_rejects_unmapped_v2_indirect_metadata(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][1]]
    data["edges"][0]["source"]["id"] = (
        "internal.shop_dm.ods_order.missing_amount"
    )

    with pytest.raises(ValueError) as exc_info:
        module.build_import_rows(
            data,
            tasks_dir=tmp_path,
            context=module.ImportContext(
                project="shop",
                snapshot_id=42,
                datasource_id=1,
                datasource_name="shop_dm",
                db_type="doris",
                host="127.0.0.1:9030",
            ),
        )

    message = str(exc_info.value)
    assert "missing_amount" in message
    assert "internal.shop_dm.ods_order" in message


def test_import_rejects_unmapped_v2_indirect_metadata_before_connecting(
    monkeypatch, tmp_path
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_v2_snapshot()
    data["edges"] = [data["edges"][1]]
    data["edges"][0]["source"]["id"] = (
        "internal.shop_dm.ods_order.missing_amount"
    )
    lineage_file = tmp_path / "lineage_data.json"
    lineage_file.write_text(json.dumps(data), encoding="utf-8")
    connection_opened = False

    def fail_if_connected(*_args, **_kwargs):
        nonlocal connection_opened
        connection_opened = True
        pytest.fail("database connection must not be opened")

    monkeypatch.setattr(module, "_open_connection", fail_if_connected)

    with pytest.raises(ValueError) as exc_info:
        module.import_lineage(
            project="shop",
            lineage_file=lineage_file,
            snapshot_id=42,
        )

    assert connection_opened is False
    message = str(exc_info.value)
    assert "missing_amount" in message
    assert "internal.shop_dm.ods_order" in message


def test_build_import_rows_keeps_v1_indirect_metadata_skip_behavior(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = _demo_snapshot()
    data["edges"] = [data["edges"][1]]
    data["edges"][0]["source"]["id"] = "ods_order.missing_amount"

    rows = module.build_import_rows(
        data,
        tasks_dir=tmp_path,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.indirect_lineage_rows == []
    assert len(rows.skipped_edges) == 1
    assert rows.skipped_edges[0].source == "ods_order.missing_amount"
    assert rows.skipped_edges[0].target == "dwd_order_detail"
    assert rows.skipped_edges[0].reason == (
        "source, target, or job metadata is missing"
    )


def test_build_import_rows_matches_mixed_case_edge_refs_to_metadata(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "dwd_order_detail.sql").write_text("", encoding="utf-8")
    data = _demo_snapshot()
    data["edges"][0]["source"]["id"] = "ODS_ORDER.AMOUNT"
    data["edges"][0]["target"]["id"] = "DWD_ORDER_DETAIL.AMOUNT"
    data["edges"][1]["source"]["id"] = "ODS_ORDER.AMOUNT"
    data["edges"][1]["target"]["id"] = "DWD_ORDER_DETAIL"

    rows = module.build_import_rows(
        data,
        tasks_dir=tasks_dir,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert rows.column_lineage_rows == [
        (1, 42, 1, 1, 2, 2, 1, "DIRECT", "", "amount")
    ]
    assert rows.indirect_lineage_rows == [
        (1, 42, 1, 1, 2, 1, "FILTER", "amount > 0")
    ]
    assert rows.skipped_edges == []


def test_v1_normalizer_keeps_same_basename_source_paths_as_distinct_jobs(
    tmp_path,
):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )
    data = {
        "tables": [
            {
                "name": table_name,
                "columns": [{"name": "id", "type": "BIGINT"}],
            }
            for table_name in ("src_a", "out_a", "src_b", "out_b")
        ],
        "edges": [
            {
                "source": "src_a.id",
                "target": "out_a.id",
                "relation_type": "direct",
                "source_file": "mid/tasks/build.sql",
            },
            {
                "source": "src_b.id",
                "target": "out_b.id",
                "relation_type": "direct",
                "source_file": "ads/tasks/build.sql",
            },
        ],
    }

    rows = module.build_import_rows(
        data,
        tasks_dir=tmp_path,
        context=module.ImportContext(
            project="shop",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="shop_dm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    assert [row[2:4] for row in rows.job_rows] == [
        ("ads/tasks/build", "ads/tasks/build.sql"),
        ("mid/tasks/build", "mid/tasks/build.sql"),
    ]
    assert [row[6] for row in rows.column_lineage_rows] == [2, 1]


def test_bulk_insert_uses_executemany_in_chunks():
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []
            self.executemany_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def executemany(self, sql, rows):
            self.executemany_calls.append((sql, list(rows)))

    cursor = RecordingCursor()

    inserted = module.bulk_insert(
        cursor,
        "INSERT INTO demo VALUES (%s)",
        [(1,), (2,), (3,)],
        batch_size=2,
    )

    assert inserted == 3
    assert cursor.execute_calls == []
    assert cursor.executemany_calls == [
        ("INSERT INTO demo VALUES (%s)", [(1,), (2,)]),
        ("INSERT INTO demo VALUES (%s)", [(3,)]),
    ]


def test_delete_snapshot_rows_does_not_truncate_whole_lineage_database():
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []
            self.executemany_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def executemany(self, sql, rows):
            self.executemany_calls.append((sql, list(rows)))

    cursor = RecordingCursor()

    module.delete_snapshot_rows(cursor, snapshot_id=42)

    assert cursor.execute_calls == [
        ("DELETE FROM indirect_lineage WHERE snapshot_id = %s", (42,)),
        (
            "DELETE FROM non_column_direct_lineage WHERE snapshot_id = %s",
            (42,),
        ),
        ("DELETE FROM column_lineage WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM table_lineage WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM job_dataset WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM job WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM column_info WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM table_info WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM datasource WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM lineage_snapshot WHERE id = %s", (42,)),
    ]


def test_migrate_lineage_schema_drops_legacy_table_layer_column():
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def fetchall(self):
            return [
                ("id",),
                ("snapshot_id",),
                ("layer",),
                ("table_name",),
            ]

    cursor = RecordingCursor()

    module.migrate_lineage_schema(cursor)

    assert cursor.execute_calls == [
        ("SHOW COLUMNS FROM table_info", None),
        ("ALTER TABLE table_info DROP COLUMN layer", None),
    ]


def test_migrate_lineage_schema_leaves_current_table_info_schema():
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def fetchall(self):
            return [
                {"Field": "id"},
                {"Field": "snapshot_id"},
                {"Field": "table_name"},
            ]

    cursor = RecordingCursor()

    module.migrate_lineage_schema(cursor)

    assert cursor.execute_calls == [
        ("SHOW COLUMNS FROM table_info", None),
    ]


def test_insert_and_verify_include_non_column_direct_lineage(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []
            self.executemany_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def executemany(self, sql, rows):
            self.executemany_calls.append((sql, list(rows)))

    rows = module.LineageImportRows(
        table_rows=[(1,)],
        column_rows=[(1,), (2,)],
        job_rows=[(1,)],
        job_dataset_rows=[(1,), (2,)],
        non_column_direct_lineage_rows=[
            (
                1,
                42,
                2,
                2,
                1,
                "DIRECT",
                "constant",
                "'ALL'",
                "literal",
                '{"type":"literal","value":"ALL"}',
            )
        ],
    )
    cursor = RecordingCursor()

    counts = module._insert_all(cursor, rows=rows, batch_size=10)

    module.insert_snapshot_row(
        cursor,
        snapshot_id=42,
        project="shop",
        source_path=tmp_path / "lineage_data.json",
        status="IMPORTED",
        is_active=0,
        rows=rows,
    )

    sql, params = cursor.execute_calls[0]
    assert "job_dataset_count" in sql
    assert "non_column_direct_lineage_count" in sql
    assert params[8] == 2
    assert params[10] == 1
    assert counts["non_column_direct_lineage"] == 1
    insert_sql, insert_rows = next(
        (sql, inserted_rows)
        for sql, inserted_rows in cursor.executemany_calls
        if "INSERT INTO non_column_direct_lineage" in sql
    )
    assert "source_payload" in insert_sql
    assert insert_rows == rows.non_column_direct_lineage_rows
    assert "job_dataset" in module.VERIFY_TABLES
    assert "non_column_direct_lineage" in module.VERIFY_TABLES

    class CountCursor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

        def fetchone(self):
            return (1,)

    count_cursor = CountCursor()
    verified_counts = module._verify_counts(count_cursor, snapshot_id=42)

    assert verified_counts["non_column_direct_lineage"] == 1
    assert (
        "SELECT COUNT(*) FROM non_column_direct_lineage "
        "WHERE snapshot_id = %s",
        (42,),
    ) in count_cursor.execute_calls
