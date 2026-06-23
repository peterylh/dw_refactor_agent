import json
import types

import sqlglot

import lineage.lineage_extractor as lineage_extractor
from lineage.lineage_extractor import build_schema_from_texts


def _schema_table_count(schema):
    mapping = getattr(schema, "mapping", schema)
    return sum(1 for _ in lineage_extractor._iter_schema_tables(mapping))


def test_extract_lineage_prunes_schema_before_calling_sqlglot_lineage(
    monkeypatch,
):
    unused_ddls = [
        f"""
        CREATE TABLE shop_dm.unused_{index} (
            id BIGINT,
            value VARCHAR(10)
        )
        """
        for index in range(20)
    ]
    schema = build_schema_from_texts(
        [
            """
            CREATE TABLE shop_dm.ods_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
            """
            CREATE TABLE shop_dm.dwd_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
            *unused_ddls,
        ]
    )
    seen_table_counts = []

    def fake_lineage(column, sql, schema, dialect, **kwargs):
        seen_table_counts.append(_schema_table_count(schema))
        projection = next(
            item for item in sql.expressions if item.alias_or_name == column
        )
        return types.SimpleNamespace(expression=projection, downstream=[])

    monkeypatch.setattr(lineage_extractor, "lineage", fake_lineage)

    entries = lineage_extractor.extract_lineage_from_sql(
        """
        INSERT INTO shop_dm.dwd_order
        SELECT order_id, amount FROM shop_dm.ods_order
        """,
        "dwd_order.sql",
        schema,
    )

    assert entries
    assert seen_table_counts == [2, 2]


def test_lineage_nodes_for_select_reuses_scope_across_output_columns(
    monkeypatch,
    schema_ods_order,
):
    scopes = []
    sql_expressions = []
    trim_selects_values = []

    def fake_lineage(
        column,
        sql,
        schema,
        dialect,
        scope=None,
        trim_selects=None,
    ):
        scopes.append(scope)
        sql_expressions.append(sql)
        trim_selects_values.append(trim_selects)
        projection = next(
            item for item in sql.expressions if item.alias_or_name == column
        )
        return types.SimpleNamespace(expression=projection, downstream=[])

    monkeypatch.setattr(lineage_extractor, "lineage", fake_lineage)

    lineage_extractor._lineage_nodes_for_select(
        sqlglot.parse_one(
            """
            SELECT order_id, customer_id
            FROM shop_dm.ods_order
            """,
            dialect="doris",
        ),
        schema_ods_order,
    )

    assert len(scopes) == 2
    assert scopes[0] is not None
    assert scopes[0] is scopes[1]
    assert sql_expressions[0] is sql_expressions[1]
    assert trim_selects_values == [False, False]


def test_lineage_scope_failure_is_reported_as_warning(
    monkeypatch,
    schema_ods_order,
):
    diagnostics = []

    def fail_scope(_select_expr, _schema):
        raise RuntimeError("scope boom")

    def fake_lineage(column, sql, schema, dialect, scope=None, **kwargs):
        projection = next(
            item for item in sql.expressions if item.alias_or_name == column
        )
        return types.SimpleNamespace(expression=projection, downstream=[])

    monkeypatch.setattr(lineage_extractor, "_lineage_scope", fail_scope)
    monkeypatch.setattr(lineage_extractor, "lineage", fake_lineage)

    lineage_extractor._lineage_nodes_for_select(
        sqlglot.parse_one(
            """
            SELECT order_id
            FROM shop_dm.ods_order
            """,
            dialect="doris",
        ),
        schema_ods_order,
        file_path="dwd_order.sql",
        target_table="dwd_order",
        diagnostics=diagnostics,
    )

    assert diagnostics == [
        {
            "source_file": "dwd_order.sql",
            "stage": "lineage_scope",
            "severity": "warning",
            "error": "RuntimeError: scope boom",
            "target_table": "dwd_order",
        }
    ]
    assert lineage_extractor._fatal_diagnostics(diagnostics) == []


def test_should_write_lineage_output_blocks_existing_file_on_fatal_error(
    tmp_path,
):
    output_path = tmp_path / "lineage_data_shop.json"
    output_path.write_text("old lineage", encoding="utf-8")

    assert not lineage_extractor._should_write_lineage_output(
        fatal_diagnostics=[{"severity": "error"}],
        output_paths=[output_path],
        force_overwrite_on_error=False,
    )


def test_should_write_lineage_output_allows_new_file_on_fatal_error(tmp_path):
    output_path = tmp_path / "lineage_data_shop.json"

    assert lineage_extractor._should_write_lineage_output(
        fatal_diagnostics=[{"severity": "error"}],
        output_paths=[output_path],
        force_overwrite_on_error=False,
    )


def test_should_write_lineage_output_allows_forced_overwrite_on_fatal_error(
    tmp_path,
):
    output_path = tmp_path / "lineage_data_shop.json"
    output_path.write_text("old lineage", encoding="utf-8")

    assert lineage_extractor._should_write_lineage_output(
        fatal_diagnostics=[{"severity": "error"}],
        output_paths=[output_path],
        force_overwrite_on_error=True,
    )


def test_build_lineage_output_indexes_schema_once(monkeypatch):
    schema = build_schema_from_texts(
        [
            """
            CREATE TABLE shop_dm.ods_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
            """
            CREATE TABLE shop_dm.dwd_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
        ]
    )
    entries = [
        {
            "source_table": "shop_dm.ods_order",
            "source_column": "amount",
            "target_table": "shop_dm.dwd_order",
            "target_column": "amount",
            "expression": "amount",
            "source_file": f"task_{index}.sql",
        }
        for index in range(20)
    ]
    original_iter_schema_tables = lineage_extractor._iter_schema_tables
    call_count = {"value": 0}

    def counting_iter_schema_tables(schema_arg):
        call_count["value"] += 1
        for item in original_iter_schema_tables(schema_arg):
            yield item

    monkeypatch.setattr(
        lineage_extractor,
        "_iter_schema_tables",
        counting_iter_schema_tables,
    )

    output = lineage_extractor.build_lineage_output(entries, schema)

    assert len(output["edges"]) == 20
    assert call_count["value"] == 1


def test_collect_statement_table_names_includes_targets_sources_and_cte_sources():
    statements = sqlglot.parse(
        """
        WITH recent_orders AS (
            SELECT order_id, customer_id FROM shop_dm.ods_order
        )
        INSERT INTO shop_dm.dwd_order
        SELECT r.order_id, c.customer_name
        FROM recent_orders r
        JOIN shop_dm.ods_customer c ON r.customer_id = c.customer_id
        """,
        dialect="doris",
    )

    names = lineage_extractor.collect_statement_table_names(statements)

    assert {
        "shop_dm.ods_order",
        "shop_dm.ods_customer",
        "shop_dm.dwd_order",
    } <= names


def test_slice_schema_keeps_matching_short_and_qualified_tables():
    schema = {
        "internal": {
            "shop_dm": {
                "ods_order": {"order_id": "BIGINT"},
                "dwd_order": {"order_id": "BIGINT"},
                "unused": {"id": "BIGINT"},
            }
        },
        "hive": {
            "archive": {
                "ods_order": {"order_id": "BIGINT"},
            }
        },
    }

    sliced = lineage_extractor.slice_schema(
        schema,
        {"shop_dm.ods_order", "dwd_order"},
    )

    assert sliced == {
        "internal": {
            "shop_dm": {
                "ods_order": {"order_id": "BIGINT"},
                "dwd_order": {"order_id": "BIGINT"},
            }
        },
        "hive": {
            "archive": {
                "ods_order": {"order_id": "BIGINT"},
            }
        },
    }


def test_schema_table_count_counts_catalog_database_table_shape():
    schema = {
        "internal": {
            "shop_dm": {
                "ods_order": {"order_id": "BIGINT"},
                "dwd_order": {"order_id": "BIGINT"},
            },
            "other": {
                "dim_city": {"city_id": "BIGINT"},
            },
        }
    }

    assert lineage_extractor.schema_table_count(schema) == 3


def test_extract_lineage_from_task_files_supports_parallelism(
    tmp_path,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    first = tasks_dir / "a.sql"
    second = tasks_dir / "b.sql"
    first.write_text(
        "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )
    second.write_text(
        "INSERT INTO t2 SELECT customer_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )

    result = lineage_extractor.extract_lineage_from_task_files(
        [first, second],
        tasks_dir,
        schema_ods_order,
        parallel=2,
    )

    assert [item["source_file"] for item in result["task_results"]] == [
        "a.sql",
        "b.sql",
    ]
    assert {
        (
            entry["source_table"],
            entry["source_column"],
            entry["target_table"],
            entry["target_column"],
        )
        for entry in result["lineage"]
        if entry.get("lineage_type") == "direct"
    } == {
        ("ods_order", "order_id", "t1", "order_id"),
        ("ods_order", "customer_id", "t2", "customer_id"),
    }


def test_extract_lineage_from_task_files_reports_task_progress(
    tmp_path,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    first = tasks_dir / "a.sql"
    second = tasks_dir / "b.sql"
    first.write_text(
        "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )
    second.write_text(
        "INSERT INTO t2 SELECT customer_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )
    events = []

    lineage_extractor.extract_lineage_from_task_files(
        [first, second],
        tasks_dir,
        schema_ods_order,
        parallel=1,
        progress_callback=lambda completed, total, result: events.append(
            (completed, total, result["source_file"], len(result["entries"]))
        ),
    )

    assert events == [
        (1, 2, "a.sql", 1),
        (2, 2, "b.sql", 1),
    ]


def test_extract_lineage_from_task_files_parses_uncached_task_once_with_cache(
    tmp_path,
    monkeypatch,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "a.sql"
    task_sql = "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order"
    task_file.write_text(task_sql, encoding="utf-8")
    original_parse = lineage_extractor.sqlglot.parse
    task_parse_count = 0

    def counted_parse(sql_text, dialect):
        nonlocal task_parse_count
        if sql_text == task_sql:
            task_parse_count += 1
        return original_parse(sql_text, dialect=dialect)

    monkeypatch.setattr(lineage_extractor.sqlglot, "parse", counted_parse)

    result = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
        previous_cache_file=tmp_path / "task_cache.json",
    )

    assert result["errors"] == []
    assert task_parse_count == 1
    assert result["task_cache"] is not None


def test_extract_lineage_from_task_files_uses_cache_metadata_without_sql_parse(
    tmp_path,
    monkeypatch,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "a.sql"
    task_sql = "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order"
    task_file.write_text(task_sql, encoding="utf-8")
    cache_path = tmp_path / "task_cache.json"

    cold = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
        previous_cache_file=cache_path,
    )
    cache_path.write_text(json.dumps(cold["task_cache"]), encoding="utf-8")

    original_parse = lineage_extractor.sqlglot.parse

    task_parse_count = 0

    def counted_parse(sql_text, dialect):
        nonlocal task_parse_count
        if sql_text == task_sql:
            task_parse_count += 1
        return original_parse(sql_text, dialect=dialect)

    monkeypatch.setattr(lineage_extractor.sqlglot, "parse", counted_parse)

    warm = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
        previous_cache_file=cache_path,
    )

    assert warm["errors"] == []
    assert warm["task_results"][0]["cache_hit"] is True
    assert task_parse_count == 0


def test_extract_lineage_from_task_files_reports_parse_errors(
    tmp_path,
    monkeypatch,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "broken.sql"
    task_file.write_text("SELECT (", encoding="utf-8")

    def fail_parse(_sql_text, dialect):
        raise ValueError("bad sql")

    monkeypatch.setattr(lineage_extractor.sqlglot, "parse", fail_parse)

    result = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
    )

    assert result["lineage"] == []
    assert result["errors"] == [
        {
            "source_file": "broken.sql",
            "stage": "parse",
            "severity": "error",
            "error": "ValueError: bad sql",
        }
    ]
    assert result["task_results"][0]["errors"] == result["errors"]


def test_extract_lineage_reports_failed_task_and_column(
    tmp_path,
    monkeypatch,
):
    schema = build_schema_from_texts(
        [
            """
            CREATE TABLE shop_dm.ods_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
            """
            CREATE TABLE shop_dm.dwd_order (
                order_id BIGINT,
                amount DECIMAL(12,2)
            )
            """,
        ]
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "dwd_order.sql"
    task_file.write_text(
        """
        INSERT INTO shop_dm.dwd_order
        SELECT order_id, amount FROM shop_dm.ods_order
        """,
        encoding="utf-8",
    )

    def flaky_lineage(column, sql, schema, dialect, **kwargs):
        if column == "amount":
            raise RuntimeError("lineage boom")
        projection = next(
            item for item in sql.expressions if item.alias_or_name == column
        )
        return types.SimpleNamespace(expression=projection, downstream=[])

    monkeypatch.setattr(lineage_extractor, "lineage", flaky_lineage)

    result = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema,
        parallel=1,
    )

    assert result["errors"] == [
        {
            "source_file": "dwd_order.sql",
            "stage": "lineage_column",
            "severity": "error",
            "error": "RuntimeError: lineage boom",
            "target_table": "dwd_order",
            "target_column": "amount",
            "expression": "amount",
        }
    ]


def test_extract_lineage_from_task_files_reports_unhandled_task_errors(
    tmp_path,
    monkeypatch,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "bad_worker.sql"
    task_file.write_text(
        "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )

    def fail_task(_work_item, _schema):
        raise RuntimeError("unexpected boom")

    monkeypatch.setattr(
        lineage_extractor, "_extract_task_work_item", fail_task
    )

    result = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
    )

    assert result["errors"] == [
        {
            "source_file": "bad_worker.sql",
            "stage": "worker",
            "severity": "error",
            "error": "RuntimeError: unexpected boom",
        }
    ]
