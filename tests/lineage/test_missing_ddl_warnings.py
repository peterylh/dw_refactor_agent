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


def test_extract_lineage_missing_ddl_ignores_case_variant_transient_drop(
    tmp_path,
):
    tasks_dir, task_file = _write_task(
        tmp_path,
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
    )
    schema = {
        "internal": {
            "shop_dm": {
                "i00_trade_engine_prod_mapping": {
                    "prod_id": "BIGINT",
                    "prod_nm": "STRING",
                    "prod_lvl": "STRING",
                    "f_prod_id": "BIGINT",
                    "f_prod_nm": "STRING",
                    "f_prod_lvl": "STRING",
                },
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_ignores_commented_create_target(
    tmp_path,
):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "a_ibank.sql",
        """
        DROP TABLE IF EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base FORCE;

        CREATE TABLE IF NOT EXISTS tmp_A_IBANK_CUST_IND_D__20260601_5_base
        /* 算收入 */ AS
        SELECT order_id
        FROM cdm.dwd_orders;
        """,
    )
    schema = {
        "internal": {
            "cdm": {
                "dwd_orders": {"order_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_ignores_drop_only_table(tmp_path):
    tasks_dir, task_file = _write_task(
        tmp_path,
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
    )
    schema = {
        "internal": {
            "shop_dm": {
                "r_yygl_regional_customer_01": {"cust_id": "BIGINT"},
                "r_yygl_regional_customer_04": {"cust_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_ignores_create_table_target(tmp_path):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "regional_customer.sql",
        """
        CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1
        DISTRIBUTED BY RANDOM BUCKETS 15 AS
        SELECT cust_id
        FROM r_yygl_regional_customer_01;
        """,
    )
    schema = {
        "internal": {
            "shop_dm": {
                "r_yygl_regional_customer_01": {"cust_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_ignores_table_created_in_same_task(
    tmp_path,
):
    tasks_dir, task_file = _write_task(
        tmp_path,
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
    )
    schema = {
        "internal": {
            "shop_dm": {
                "r_yygl_regional_customer_01": {"cust_id": "BIGINT"},
            }
        }
    }

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema)

    assert result["missing_ddl_tables"] == []
    assert result["task_results"][0]["missing_ddl_tables"] == []


def test_extract_lineage_missing_ddl_still_reports_create_table_sources(
    tmp_path,
):
    tasks_dir, task_file = _write_task(
        tmp_path,
        "regional_customer.sql",
        """
        CREATE TABLE IF NOT EXISTS tmp_R_YYGL_REGIONAL_CUSTOMER_04_20260602_1
        DISTRIBUTED BY RANDOM BUCKETS 15 AS
        SELECT cust_id
        FROM r_yygl_regional_customer_01;
        """,
    )

    result = extract_lineage_from_task_files([task_file], tasks_dir, schema={})

    assert result["missing_ddl_tables"] == ["r_yygl_regional_customer_01"]
    assert result["task_results"][0]["missing_ddl_tables"] == [
        "r_yygl_regional_customer_01",
    ]


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
