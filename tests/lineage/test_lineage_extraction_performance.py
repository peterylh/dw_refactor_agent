import importlib.util
import inspect
import json
import pickle
import sys
import types
from pathlib import Path

import sqlglot

import dw_refactor_agent.lineage.lineage_extractor as lineage_extractor
import dw_refactor_agent.lineage.task_cache as task_cache
from dw_refactor_agent.lineage import (
    lineage_output,
    lineage_projection,
    lineage_schema,
    lineage_tasks,
    lineage_trace,
)
from dw_refactor_agent.lineage.lineage_extractor import build_schema_from_texts

_SPLIT_IMPLEMENTATION_MODULES = (
    lineage_schema,
    lineage_projection,
    lineage_trace,
    lineage_tasks,
    lineage_output,
)


def _schema_table_count(schema):
    mapping = getattr(schema, "mapping", schema)
    return sum(1 for _ in lineage_extractor._iter_schema_tables(mapping))


def test_extractor_hash_includes_split_modules(monkeypatch):
    captured = {}

    def capture_paths(paths):
        captured["paths"] = tuple(paths)
        return "split-extractor-hash"

    monkeypatch.setattr(
        task_cache,
        "extractor_version_hash",
        capture_paths,
    )

    assert (
        lineage_extractor._extractor_hash_for_cache() == "split-extractor-hash"
    )
    assert [Path(path).name for path in captured["paths"]] == [
        "lineage_extractor.py",
        "lineage_schema.py",
        "lineage_trace.py",
        "lineage_tasks.py",
        "lineage_projection.py",
        "runtime_binding.py",
        "sql_task_facts.py",
    ]


def test_split_lineage_modules_stay_below_policy_limit():
    module_paths = (
        Path(lineage_extractor.__file__),
        Path(lineage_schema.__file__),
        Path(lineage_trace.__file__),
        Path(lineage_tasks.__file__),
        Path(lineage_projection.__file__),
        Path(lineage_output.__file__),
    )

    assert {
        path.name: len(path.read_text(encoding="utf-8").splitlines())
        for path in module_paths
        if len(path.read_text(encoding="utf-8").splitlines()) >= 3000
    } == {}


def test_projection_peer_calls_observe_facade_monkeypatch(monkeypatch):
    query = sqlglot.parse_one("SELECT order_id")
    monkeypatch.setattr(
        lineage_extractor,
        "_projection_output_name",
        lambda _projection: "patched_order_id",
    )

    assert lineage_extractor._projection_output_names(query) == [
        "patched_order_id"
    ]


def test_split_projection_module_is_directly_callable():
    query = sqlglot.parse_one("SELECT order_id")

    assert lineage_projection._projection_output_names(query) == ["order_id"]


def test_split_core_modules_are_directly_callable():
    schema = lineage_schema.build_schema_from_texts(
        ["CREATE TABLE shop_dm.orders (order_id BIGINT)"]
    )
    update = sqlglot.parse_one(
        "UPDATE shop_dm.orders SET order_id = 1",
        dialect="doris",
    )

    assert lineage_schema.schema_table_count(schema) == 1
    assert lineage_trace.update_to_select(update).expressions[0].alias == (
        "order_id"
    )
    assert lineage_tasks._task_fact_result_fields(
        {"input_tables": {"shop_dm.orders"}}
    )["input_tables"] == ["shop_dm.orders"]


def test_split_projection_bindings_are_runtime_local(monkeypatch):
    query = sqlglot.parse_one("SELECT order_id")
    monkeypatch.setattr(
        lineage_extractor,
        "_projection_output_name",
        lambda _projection: "canonical_order_id",
    )
    alternate_runtime = types.SimpleNamespace(
        _projection_output_name=lambda _projection: "alternate_order_id",
    )

    assert lineage_extractor._projection_output_names(query) == [
        "canonical_order_id"
    ]
    assert lineage_projection.call(
        "_projection_output_names",
        alternate_runtime,
        query,
    ) == ["alternate_order_id"]
    assert lineage_extractor._projection_output_names(query) == [
        "canonical_order_id"
    ]


def test_split_facade_functions_remain_picklable():
    for module in _SPLIT_IMPLEMENTATION_MODULES:
        for name in module._EXPORTED_FUNCTIONS:
            facade = getattr(lineage_extractor, name)
            assert pickle.loads(pickle.dumps(facade)) is facade


def test_split_facade_functions_preserve_callable_metadata():
    for module in _SPLIT_IMPLEMENTATION_MODULES:
        for name in module._EXPORTED_FUNCTIONS:
            facade = getattr(lineage_extractor, name)
            implementation = getattr(module, name)
            assert inspect.signature(facade) == inspect.signature(
                implementation
            )
            assert facade.__doc__ == implementation.__doc__
            assert facade.__annotations__ == implementation.__annotations__


def test_split_task_classes_keep_extractor_pickle_identity():
    work_item = lineage_extractor.TaskWorkItem(
        index=1,
        source_file="orders.sql",
        sql_text="SELECT 1",
    )

    assert issubclass(
        lineage_extractor.TaskWorkItem,
        lineage_tasks.TaskWorkItem,
    )
    assert pickle.loads(pickle.dumps(work_item)) == work_item


def test_split_facades_keep_classes_and_stats_runtime_local():
    alternate_name = (
        "dw_refactor_agent.lineage.lineage_extractor_alternate_test"
    )
    spec = importlib.util.spec_from_file_location(
        alternate_name,
        lineage_extractor.__file__,
    )
    alternate = importlib.util.module_from_spec(spec)
    sys.modules[alternate_name] = alternate
    try:
        spec.loader.exec_module(alternate)
        canonical_item = lineage_extractor.TaskWorkItem(
            index=1,
            source_file="orders.sql",
            sql_text="SELECT 1",
        )

        assert lineage_extractor.TaskWorkItem.__module__ == (
            lineage_extractor.__name__
        )
        assert alternate.TaskWorkItem.__module__ == alternate_name
        assert lineage_extractor.STATS is not alternate.STATS

        lineage_extractor._reset_stats()
        alternate._reset_stats()
        alternate.STATS["parse_failures"] = 3
        assert lineage_extractor.STATS["parse_failures"] == 0

        payload = pickle.dumps(canonical_item)
        sys.modules.pop(alternate_name)
        assert pickle.loads(payload) == canonical_item
    finally:
        sys.modules.pop(alternate_name, None)


def test_split_schema_non_function_dependencies_observe_facade_monkeypatch(
    monkeypatch,
):
    class PatchedLookup:
        def __init__(self, schema):
            self.schema = schema

        def table_name(self, table_name):
            return table_name

        def column_name(self, _table_name, column_name):
            return column_name

    class NeverAggregate:
        @staticmethod
        def search(_expression):
            return None

    captured = {}

    class CapturingMappingSchema:
        def __init__(self, mapping, dialect, normalize):
            captured["mapping"] = mapping
            captured["dialect"] = dialect
            captured["normalize"] = normalize

    monkeypatch.setattr(lineage_extractor, "_SchemaLookup", PatchedLookup)
    monkeypatch.setattr(
        lineage_extractor,
        "AGGREGATE_PATTERN",
        NeverAggregate(),
    )
    monkeypatch.setattr(
        lineage_extractor,
        "LINEAGE_DIALECT",
        "custom-dialect",
    )
    monkeypatch.setattr(
        lineage_schema,
        "MappingSchema",
        CapturingMappingSchema,
    )

    lookup = lineage_extractor._schema_lookup({"table": {}})
    assert isinstance(lookup, PatchedLookup)
    assert (
        lineage_extractor._transformation_type_for_expression("SUM(amount)")
        == "passthrough"
    )
    assert isinstance(
        lineage_extractor._lineage_schema({}),
        CapturingMappingSchema,
    )
    assert captured["dialect"] == "custom-dialect"


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


def test_empty_target_lineage_failure_records_target_table(monkeypatch):
    diagnostics = []

    def no_output_columns(*_args, **_kwargs):
        return sqlglot.exp.Select(), [], False

    monkeypatch.setattr(
        lineage_extractor,
        "_expand_query_star_projections",
        no_output_columns,
    )
    monkeypatch.setattr(
        lineage_extractor,
        "_lineage_node_items_for_select",
        lambda *_args, **_kwargs: [],
    )
    lineage_extractor._reset_stats()

    try:
        entries = lineage_extractor._trace_lineage(
            "shop_dm.dwd_order",
            sqlglot.parse_one("SELECT order_id FROM shop_dm.ods_order"),
            {},
            "dwd_order.sql",
            diagnostics=diagnostics,
        )

        assert entries == []
        assert lineage_extractor.STATS["lineage_failures"] == 1
        assert diagnostics == [
            {
                "source_file": "dwd_order.sql",
                "stage": "lineage_target",
                "severity": "warning",
                "error": (
                    "ValueError: No lineage nodes or output columns extracted"
                ),
                "target_table": "dwd_order",
            }
        ]
        assert lineage_extractor._fatal_diagnostics(diagnostics) == []
    finally:
        lineage_extractor._reset_stats()


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


def test_unqualified_table_uses_current_database_only(monkeypatch):
    monkeypatch.setattr(lineage_extractor, "CURRENT_CATALOG", "internal")
    monkeypatch.setattr(lineage_extractor, "CURRENT_DB", "cdm")
    schema = {
        "internal": {
            "cdm": {
                "tdm_corp_label_measure_check_result": {"id": "BIGINT"},
                "out": {"id": "BIGINT"},
            },
            "tdm": {
                "tdm_corp_label_measure_check_result": {"id": "BIGINT"},
            },
        }
    }

    sliced = lineage_extractor.slice_schema(
        schema,
        {"tdm_corp_label_measure_check_result", "out"},
    )

    assert sliced == {
        "internal": {
            "cdm": {
                "tdm_corp_label_measure_check_result": {"id": "BIGINT"},
                "out": {"id": "BIGINT"},
            }
        }
    }

    diagnostics = []
    entries = lineage_extractor.extract_lineage_from_sql(
        """
        INSERT INTO out(id)
        SELECT id FROM tdm_corp_label_measure_check_result
        """,
        "out.sql",
        schema,
        diagnostics=diagnostics,
    )

    assert diagnostics == []
    assert any(
        entry.get("source_table") == "tdm_corp_label_measure_check_result"
        and entry.get("target_table") == "out"
        for entry in entries
    )


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


def test_parse_task_context_materializes_reusable_task_state():
    schema = build_schema_from_texts(
        [
            """
            CREATE TABLE shop_dm.ods_order (
                order_id BIGINT,
                customer_id BIGINT
            )
            """,
            """
            CREATE TABLE shop_dm.dwd_order (
                order_id BIGINT,
                customer_id BIGINT
            )
            """,
        ]
    )
    sql_text = """
    INSERT INTO shop_dm.dwd_order
    SELECT order_id, customer_id FROM shop_dm.ods_order
    """
    work_item = lineage_extractor.TaskWorkItem(
        index=0,
        source_file="dwd_order.sql",
        sql_text=sql_text,
    )

    context = lineage_extractor._parse_task_context(work_item, schema)
    entries = lineage_extractor.extract_lineage_from_context(context)

    assert context.source_file == "dwd_order.sql"
    assert context.sql_hash
    assert context.task_facts["output_tables"] == {"shop_dm.dwd_order"}
    assert context.referenced_tables == (
        "shop_dm.dwd_order",
        "shop_dm.ods_order",
    )
    assert context.missing_ddl_tables == []
    assert lineage_extractor.schema_table_count(context.task_schema) == 2
    assert {
        (
            entry["source_table"],
            entry["source_column"],
            entry["target_table"],
            entry["target_column"],
        )
        for entry in entries
        if entry.get("lineage_type") == "direct"
    } == {
        ("ods_order", "order_id", "dwd_order", "order_id"),
        ("ods_order", "customer_id", "dwd_order", "customer_id"),
    }


def test_task_cache_metadata_is_built_from_parsed_context():
    schema = build_schema_from_texts(
        [
            """
            CREATE TABLE shop_dm.ods_order (
                order_id BIGINT
            )
            """,
            """
            CREATE TABLE shop_dm.dwd_order (
                order_id BIGINT
            )
            """,
        ]
    )
    work_item = lineage_extractor.TaskWorkItem(
        index=0,
        source_file="dwd_order.sql",
        sql_text=(
            "INSERT INTO shop_dm.dwd_order "
            "SELECT order_id FROM shop_dm.ods_order"
        ),
    )
    context = lineage_extractor._parse_task_context(work_item, schema)

    metadata = lineage_extractor._task_cache_metadata_from_context(
        context,
        schema,
        project="shop",
        extractor_hash="extractor-v1",
    )
    cache_key = lineage_extractor._task_cache_key_from_metadata(
        context.work_item,
        project="shop",
        metadata=metadata,
    )
    cache_result = lineage_extractor._result_with_cache_metadata(
        {
            "source_file": "dwd_order.sql",
            "entries": [],
            "transient_tables": [],
            "missing_ddl_tables": [],
            "stats": {},
            "errors": [],
        },
        metadata,
    )

    assert metadata.sql_hash == context.sql_hash
    assert metadata.referenced_tables == context.referenced_tables
    assert metadata.extractor_hash == "extractor-v1"
    assert metadata.schema_slice_hash
    assert cache_key
    assert cache_result["sql_hash"] == metadata.sql_hash
    assert cache_result["referenced_tables"] == list(
        metadata.referenced_tables
    )
    assert cache_result["schema_slice_hash"] == metadata.schema_slice_hash


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
    assert cold["task_results"][0]["input_tables"] == ["shop_dm.ods_order"]
    assert cold["task_results"][0]["output_tables"] == ["t1"]
    assert cold["task_results"][0]["created_tables"] == []
    assert cold["task_results"][0]["temporary_tables"] == []
    assert cold["task_results"][0]["local_lifecycle_tables"] == []
    assert cold["task_cache"]["format_version"] == 3
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
    assert warm["task_results"][0]["input_tables"] == ["shop_dm.ods_order"]
    assert warm["task_results"][0]["output_tables"] == ["t1"]
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


def test_extract_lineage_from_task_files_reports_context_errors_as_worker(
    tmp_path,
    monkeypatch,
    schema_ods_order,
):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    task_file = tasks_dir / "a.sql"
    task_file.write_text(
        "INSERT INTO t1 SELECT order_id FROM shop_dm.ods_order",
        encoding="utf-8",
    )

    def fail_task_facts(_statements, _source_file, **_kwargs):
        raise RuntimeError("task facts boom")

    monkeypatch.setattr(
        lineage_extractor,
        "extract_task_table_facts_from_statements",
        fail_task_facts,
    )

    result = lineage_extractor.extract_lineage_from_task_files(
        [task_file],
        tasks_dir,
        schema_ods_order,
        parallel=1,
    )

    assert result["lineage"] == []
    assert result["errors"] == [
        {
            "source_file": "a.sql",
            "stage": "worker",
            "severity": "error",
            "error": "RuntimeError: task facts boom",
        }
    ]


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
