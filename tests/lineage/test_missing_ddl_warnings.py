import json

import pytest

from dw_refactor_agent.lineage.lineage_extractor import (
    extract_lineage_from_task_files,
    format_missing_ddl_warnings,
)


def _write_task(tmp_path, name, sql):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    task_file = tasks_dir / name
    task_file.write_text(sql, encoding="utf-8")
    return tasks_dir, task_file


def _assert_missing_result(
    result,
    expected_missing,
    expected_sources=None,
    expected_targets=None,
    message=None,
):
    expected_sources = (
        expected_missing if expected_sources is None else (expected_sources)
    )
    expected_targets = (
        expected_missing if expected_targets is None else (expected_targets)
    )

    assert result["missing_ddl_tables"] == expected_missing, message
    assert result["missing_source_ddl"] == expected_sources, message
    assert result["missing_target_ddl"] == expected_targets, message
    assert result["task_results"][0]["missing_ddl_tables"] == (
        expected_missing
    ), message
    assert result["task_results"][0]["missing_source_ddl"] == (
        expected_sources
    ), message
    assert result["task_results"][0]["missing_target_ddl"] == (
        expected_targets
    ), message


def _shop_schema(tables):
    return {"internal": {"shop_dm": tables}}


@pytest.mark.parametrize("parallel", [1, 2])
def test_cross_job_process_schema_propagates_before_missing_ddl_checks(
    tmp_path,
    parallel,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_sql = {
        "producer.sql": """
            DROP TABLE IF EXISTS shop_dm.Stage_A;
            CREATE TABLE shop_dm.Stage_A AS
            SELECT order_id, amount
            FROM shop_dm.ods_order;
        """,
        "middle.sql": """
            DROP TABLE IF EXISTS shop_dm.STAGE_B;
            CREATE TABLE shop_dm.STAGE_B AS
            SELECT a.*
            FROM shop_dm.stage_a AS a;
        """,
        "consumer.sql": """
            INSERT INTO shop_dm.ads_order(order_id, amount)
            SELECT b.*
            FROM shop_dm.stage_b AS b;
        """,
    }
    task_files = {}
    for name, sql in task_sql.items():
        task_file = tasks_dir / name
        task_file.write_text(sql, encoding="utf-8")
        task_files[name] = task_file

    result = extract_lineage_from_task_files(
        [
            task_files["consumer.sql"],
            task_files["middle.sql"],
            task_files["producer.sql"],
        ],
        tasks_dir,
        _shop_schema(
            {
                "ods_order": {
                    "order_id": "BIGINT",
                    "amount": "DECIMAL(18, 2)",
                },
                "ads_order": {
                    "order_id": "BIGINT",
                    "amount": "DECIMAL(18, 2)",
                },
            }
        ),
        parallel=parallel,
    )

    by_source = {
        task_result["source_file"]: task_result
        for task_result in result["task_results"]
    }
    assert result["missing_ddl_tables"] == []
    assert by_source["middle.sql"]["missing_source_ddl"] == []
    assert by_source["consumer.sql"]["missing_source_ddl"] == []
    assert result["errors"] == []
    assert {
        (
            entry.get("source_table"),
            entry.get("source_column"),
            entry.get("target_table"),
            entry.get("target_column"),
        )
        for entry in by_source["consumer.sql"]["entries"]
        if entry.get("lineage_type") == "direct"
    } == {
        ("STAGE_B", "order_id", "ads_order", "order_id"),
        ("STAGE_B", "amount", "ads_order", "amount"),
    }


def test_process_schema_change_invalidates_cached_downstream_task(tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    producer = tasks_dir / "producer.sql"
    consumer = tasks_dir / "consumer.sql"
    cache_path = tmp_path / "task_cache.json"
    producer.write_text(
        """
        CREATE TABLE shop_dm.stage_a AS
        SELECT order_id FROM shop_dm.ods_order;
        """,
        encoding="utf-8",
    )
    consumer.write_text(
        """
        CREATE TABLE shop_dm.stage_b AS
        SELECT * FROM shop_dm.stage_a;
        """,
        encoding="utf-8",
    )
    schema = _shop_schema(
        {
            "ods_order": {
                "order_id": "BIGINT",
                "amount": "DECIMAL(18, 2)",
            }
        }
    )

    cold = extract_lineage_from_task_files(
        [consumer, producer],
        tasks_dir,
        schema,
        previous_cache_file=cache_path,
    )
    cache_path.write_text(json.dumps(cold["task_cache"]), encoding="utf-8")
    producer.write_text(
        """
        CREATE TABLE shop_dm.stage_a AS
        SELECT order_id, amount FROM shop_dm.ods_order;
        """,
        encoding="utf-8",
    )

    warm = extract_lineage_from_task_files(
        [consumer, producer],
        tasks_dir,
        schema,
        previous_cache_file=cache_path,
    )

    by_source = {
        task_result["source_file"]: task_result
        for task_result in warm["task_results"]
    }
    assert warm["missing_ddl_tables"] == []
    assert "cache_hit" not in by_source["producer.sql"]
    assert "cache_hit" not in by_source["consumer.sql"]
    assert by_source["consumer.sql"]["process_table_schemas"] == [
        {
            "name": "internal.shop_dm.stage_b",
            "columns": {
                "order_id": "UNKNOWN",
                "amount": "UNKNOWN",
            },
        }
    ]


def test_extract_lineage_ignores_non_persistent_or_declared_tables(tmp_path):
    scenarios = [
        (
            "transient_created_and_dropped",
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
            _shop_schema(
                {
                    "dwd_orders": {"order_id": "BIGINT"},
                    "dws_orders": {"order_id": "BIGINT"},
                }
            ),
        ),
        (
            "case_variant_transient_drop",
            "tmp_prod_mapping.sql",
            """
            DROP TABLE IF EXISTS tmp_trade_engine_prod_mapping_LV7to5 FORCE;

            DROP TABLE IF EXISTS tmp_trade_engine_prod_mapping_LV7to5 FORCE;

            CREATE TABLE IF NOT EXISTS tmp_trade_engine_prod_mapping_lv7to5
            DISTRIBUTED BY RANDOM BUCKETS 15 AS
            SELECT
              t1.prod_id,
              t1.prod_nm,
              t1.prod_lvl,
              t2.f_prod_id,
              t2.f_prod_nm,
              t2.f_prod_lvl
            FROM i00_trade_engine_prod_mapping AS t1
            LEFT JOIN i00_trade_engine_prod_mapping AS t2
              ON t1.f_prod_id = t2.prod_id
            WHERE
              t1.prod_lvl = '7';
            """,
            _shop_schema(
                {
                    "i00_trade_engine_prod_mapping": {
                        "prod_id": "BIGINT",
                        "prod_nm": "STRING",
                        "prod_lvl": "STRING",
                        "f_prod_id": "BIGINT",
                        "f_prod_nm": "STRING",
                        "f_prod_lvl": "STRING",
                    },
                }
            ),
        ),
        (
            "commented_create_target",
            "a_ibank.sql",
            """
            DROP TABLE IF EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base FORCE;

            CREATE TABLE IF NOT EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base
            /* 算收入 */ AS
            SELECT order_id
            FROM cdm.dwd_orders;
            """,
            {"internal": {"cdm": {"dwd_orders": {"order_id": "BIGINT"}}}},
        ),
        (
            "drop_only_table",
            "regional_customer.sql",
            """
            DROP TABLE IF EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_0 FORCE;

            /* CREATE TABLE tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_0 AS
            SELECT *
            FROM ignored_source;
            */

            INSERT INTO r_yygl_regional_customer_04 (cust_id)
            SELECT cust_id
            FROM r_yygl_regional_customer_01;
            """,
            _shop_schema(
                {
                    "r_yygl_regional_customer_01": {"cust_id": "BIGINT"},
                    "r_yygl_regional_customer_04": {"cust_id": "BIGINT"},
                }
            ),
        ),
        (
            "create_table_target",
            "regional_customer.sql",
            """
            CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1
            DISTRIBUTED BY RANDOM BUCKETS 15 AS
            SELECT cust_id
            FROM r_yygl_regional_customer_01;
            """,
            _shop_schema(
                {"r_yygl_regional_customer_01": {"cust_id": "BIGINT"}}
            ),
        ),
        (
            "table_created_in_same_task",
            "regional_customer.sql",
            """
            CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1
            DISTRIBUTED BY RANDOM BUCKETS 15 AS
            SELECT cust_id
            FROM r_yygl_regional_customer_01;

            CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_2
            DISTRIBUTED BY RANDOM BUCKETS 15 AS
            SELECT cust_id
            FROM tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1;
            """,
            _shop_schema(
                {"r_yygl_regional_customer_01": {"cust_id": "BIGINT"}}
            ),
        ),
        (
            "cte_names",
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
            _shop_schema(
                {
                    "dwd_order": {"order_id": "BIGINT"},
                    "ods_order": {"order_id": "BIGINT"},
                }
            ),
        ),
    ]

    for scenario_name, file_name, sql, schema in scenarios:
        tasks_dir, task_file = _write_task(tmp_path, file_name, sql)
        result = extract_lineage_from_task_files(
            [task_file], tasks_dir, schema
        )

        _assert_missing_result(result, [], [], [], scenario_name)


def test_extract_lineage_reports_missing_ddl_by_statement_lifetime(tmp_path):
    scenarios = [
        (
            "empty_schema",
            "dwd_order.sql",
            """
            INSERT INTO shop_dm.dwd_order(order_id)
            SELECT o.order_id
            FROM shop_dm.ods_order o;
            """,
            {},
            ["dwd_order", "ods_order"],
            ["ods_order"],
            ["dwd_order"],
        ),
        (
            "default_db_table_with_same_created_short_name",
            "same_short_name.sql",
            """
            CREATE TABLE staging.tmp_orders AS
            SELECT id
            FROM staging.src_orders;

            INSERT INTO target_db.target_orders(id)
            SELECT id
            FROM shop_dm.tmp_orders;
            """,
            {
                "internal": {
                    "staging": {"src_orders": {"id": "BIGINT"}},
                    "target_db": {"target_orders": {"id": "BIGINT"}},
                }
            },
            ["tmp_orders"],
            ["tmp_orders"],
            [],
        ),
        (
            "table_read_before_create",
            "read_before_create.sql",
            """
            INSERT INTO shop_dm.target_orders(id)
            SELECT id
            FROM tmp_orders;

            CREATE TABLE tmp_orders AS
            SELECT id
            FROM shop_dm.src_orders;
            """,
            _shop_schema(
                {
                    "src_orders": {"id": "BIGINT"},
                    "target_orders": {"id": "BIGINT"},
                }
            ),
            ["tmp_orders"],
            ["tmp_orders"],
            [],
        ),
        (
            "create_table_source",
            "regional_customer.sql",
            """
            CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1
            DISTRIBUTED BY RANDOM BUCKETS 15 AS
            SELECT cust_id
            FROM r_yygl_regional_customer_01;
            """,
            {},
            ["r_yygl_regional_customer_01"],
            ["r_yygl_regional_customer_01"],
            [],
        ),
        (
            "dml_target",
            "dwd_order.sql",
            """
            INSERT INTO dwd_order(order_id)
            SELECT order_id
            FROM ods_order;
            """,
            _shop_schema({"ods_order": {"order_id": "BIGINT"}}),
            ["dwd_order"],
            [],
            ["dwd_order"],
        ),
        (
            "source_used_before_create",
            "ads_orders.sql",
            """
            INSERT INTO ads_orders(order_id)
            SELECT order_id
            FROM tmp_orders;

            CREATE TABLE tmp_orders AS
            SELECT order_id
            FROM ods_order;
            """,
            _shop_schema(
                {
                    "ads_orders": {"order_id": "BIGINT"},
                    "ods_order": {"order_id": "BIGINT"},
                }
            ),
            ["tmp_orders"],
            ["tmp_orders"],
            [],
        ),
        (
            "source_after_drop",
            "ads_orders.sql",
            """
            CREATE TABLE tmp_orders AS
            SELECT order_id
            FROM ods_order;

            DROP TABLE tmp_orders;

            INSERT INTO ads_orders(order_id)
            SELECT order_id
            FROM tmp_orders;
            """,
            _shop_schema(
                {
                    "ads_orders": {"order_id": "BIGINT"},
                    "ods_order": {"order_id": "BIGINT"},
                }
            ),
            ["tmp_orders"],
            ["tmp_orders"],
            [],
        ),
        (
            "same_short_name_databases_distinct",
            "ads_orders.sql",
            """
            CREATE TABLE staging.tmp_orders AS
            SELECT order_id
            FROM ods_order;

            INSERT INTO ads_orders(order_id)
            SELECT order_id
            FROM shop_dm.tmp_orders;
            """,
            _shop_schema(
                {
                    "ads_orders": {"order_id": "BIGINT"},
                    "ods_order": {"order_id": "BIGINT"},
                }
            ),
            ["tmp_orders"],
            ["tmp_orders"],
            [],
        ),
    ]

    for (
        scenario_name,
        file_name,
        sql,
        schema,
        expected_missing,
        expected_sources,
        expected_targets,
    ) in scenarios:
        tasks_dir, task_file = _write_task(tmp_path, file_name, sql)
        result = extract_lineage_from_task_files(
            [task_file], tasks_dir, schema
        )

        try:
            _assert_missing_result(
                result,
                expected_missing,
                expected_sources,
                expected_targets,
            )
        except AssertionError as exc:
            raise AssertionError(scenario_name) from exc


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
