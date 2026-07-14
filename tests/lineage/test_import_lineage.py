import importlib

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

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

    cursor = RecordingCursor()

    module.delete_snapshot_rows(cursor, snapshot_id=42)

    assert cursor.execute_calls == [
        ("DELETE FROM indirect_lineage WHERE snapshot_id = %s", (42,)),
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


def test_insert_snapshot_row_counts_job_dataset_relationships(tmp_path):
    module = importlib.import_module(
        "dw_refactor_agent.lineage.import_lineage"
    )

    class RecordingCursor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, sql, params=None):
            self.execute_calls.append((sql, params))

    rows = module.LineageImportRows(
        table_rows=[(1,)],
        column_rows=[(1,), (2,)],
        job_rows=[(1,)],
        job_dataset_rows=[(1,), (2,)],
    )
    cursor = RecordingCursor()

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
    assert params[8] == 2
    assert "job_dataset" in module.VERIFY_TABLES
