import importlib


def _demo_snapshot():
    return {
        "tables": [
            {
                "name": "ods_order",
                "full_name": "shop_dm.ods_order",
                "layer": "ODS",
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
                "layer": "DWD",
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


def test_import_lineage_module_is_safe_to_import():
    module = importlib.import_module("lineage.import_lineage")

    assert callable(module.build_parser)


def test_parser_accepts_test_db_env():
    module = importlib.import_module("lineage.import_lineage")

    args = module.build_parser().parse_args(["--project", "shop", "--db-env", "test"])

    assert args.db_env == "test"


def test_open_connection_uses_selected_db_env(monkeypatch):
    module = importlib.import_module("lineage.import_lineage")
    calls = []

    def fake_connect(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(module.pymysql, "connect", fake_connect)

    conn = module._open_connection("shop_lineage", db_env="test")

    assert conn is calls[0] or conn is not None
    assert calls == [{
        "host": "172.16.0.90",
        "port": 9034,
        "user": "root",
        "database": "shop_lineage",
        "charset": "utf8mb4",
    }]


def test_build_import_rows_normalizes_snapshot_for_database(tmp_path):
    module = importlib.import_module("lineage.import_lineage")
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
        (1, 42, 1, "ods_order", "shop_dm.ods_order", "ODS", 0, "[]"),
        (2, 42, 1, "dwd_order_detail", "shop_dm.dwd_order_detail", "DWD", 0, "[]"),
    ]
    assert rows.column_rows == [
        (1, 42, 1, "amount", "DECIMAL(12,2)", "订单金额", 0),
        (2, 42, 2, "amount", "DECIMAL(12,2)", "订单金额", 0),
    ]
    assert rows.job_rows == [(
        1,
        42,
        "dwd_order_detail",
        "dwd_order_detail.sql",
        "SQL",
        "INSERT INTO dwd_order_detail SELECT amount FROM ods_order;",
    )]
    assert rows.column_lineage_rows == [(
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
    )]
    assert rows.indirect_lineage_rows == [
        (1, 42, 1, 1, 2, 1, "FILTER", "amount > 0"),
    ]
    assert rows.table_lineage_rows == [
        (1, 42, 1, 2, 1, "DIRECT"),
        (2, 42, 1, 2, 1, "FILTER"),
    ]
    assert rows.skipped_edges == []


def test_bulk_insert_uses_executemany_in_chunks():
    module = importlib.import_module("lineage.import_lineage")

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
    module = importlib.import_module("lineage.import_lineage")

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
        ("DELETE FROM job WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM column_info WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM table_info WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM datasource WHERE snapshot_id = %s", (42,)),
        ("DELETE FROM lineage_snapshot WHERE id = %s", (42,)),
    ]
