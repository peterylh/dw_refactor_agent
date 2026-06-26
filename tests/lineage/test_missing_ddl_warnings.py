from lineage.lineage_extractor import (
    extract_lineage_from_task_files,
    format_missing_ddl_warnings,
)


def _write_task(tmp_path, name, sql):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    task_file = tasks_dir / name
    task_file.write_text(sql, encoding="utf-8")
    return tasks_dir, task_file


def test_extract_lineage_reports_tables_missing_from_schema_ddl(tmp_path):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "dwd_order.sql",
        """
        INSERT INTO shop_dm.dwd_order(order_id)
        SELECT o.order_id
        FROM shop_dm.ods_order o;
        """,
    )

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema={})

    assert result["missing_ddl_tables"] == ["dwd_order", "ods_order"]
    assert result["task_results"][0]["missing_ddl_tables"] == [
        "dwd_order",
        "ods_order",
    ]


def test_extract_lineage_missing_ddl_ignores_transient_tables(tmp_path):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "dws_orders.sql",
        """
        DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;

        CREATE TABLE shop_dm.tmp_orders_stage AS
        SELECT order_id
        FROM shop_dm.dwd_orders;

        INSERT INTO shop_dm.dws_orders(order_id)
        SELECT order_id
        FROM shop_dm.tmp_orders_stage;

        DROP TABLE IF EXISTS shop_dm.tmp_orders_stage;
        """,
    )
    schema = {
        "internal": {
            "shop_dm": {
                "dwd_orders": {"order_id": "BIGINT"},
                "dws_orders": {"order_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_ignores_cte_names(tmp_path):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "dwd_order.sql",
        """
        INSERT INTO shop_dm.dwd_order(order_id)
        WITH recent_orders AS (
            SELECT order_id
            FROM shop_dm.ods_order
        )
        SELECT order_id
        FROM recent_orders;
        """,
    )
    schema = {
        "internal": {
            "shop_dm": {
                "dwd_order": {"order_id": "BIGINT"},
                "ods_order": {"order_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_format_missing_ddl_warnings_includes_task_detail_and_summary():
    lines = format_missing_ddl_warnings(
        [
            {
                "source_file": "dwd_order.sql",
                "missing_ddl_tables": ["ods_order"],
            },
            {
                "source_file": "dws_order.sql",
                "missing_ddl_tables": ["dwd_order", "ods_order"],
            },
            {
                "source_file": "ads_order.sql",
                "missing_ddl_tables": [],
            },
        ],
        ["dwd_order", "ods_order"],
    )

    assert lines == [
        (
            "WARNING missing DDL: dwd_order.sql references ods_order, "
            "but no schema DDL was found."
        ),
        (
            "WARNING missing DDL: dws_order.sql references "
            "dwd_order, ods_order, but no schema DDL was found."
        ),
        "DDL warning: 2 referenced tables are missing from schema DDL.",
    ]
