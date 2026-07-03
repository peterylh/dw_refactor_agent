from __future__ import annotations

import inspect
import json

import dw_refactor_agent.lineage.task_cache as task_cache
from dw_refactor_agent.lineage.task_cache import (
    TaskCacheMetadata,
    cache_entry_from_result,
    load_task_cache,
    stable_json_hash,
    task_cache_key,
)


def test_task_cache_does_not_depend_on_sql_parser_or_extractor():
    source = inspect.getsource(task_cache)

    assert "import sqlglot" not in source
    assert "lineage_extractor" not in source


def test_task_cache_key_changes_when_sql_schema_or_project_config_changes():
    metadata = TaskCacheMetadata(
        sql_hash="sql-v1",
        referenced_tables=("demo_dm.dwd_order", "demo_dm.ods_order"),
        schema_slice_hash="schema-v1",
        extractor_hash="extractor-v1",
        project_config={"catalog": "internal", "db": "demo_dm"},
    )
    changed_sql = TaskCacheMetadata(
        sql_hash="sql-v2",
        referenced_tables=metadata.referenced_tables,
        schema_slice_hash=metadata.schema_slice_hash,
        extractor_hash=metadata.extractor_hash,
        project_config=metadata.project_config,
    )
    changed_schema = TaskCacheMetadata(
        sql_hash=metadata.sql_hash,
        referenced_tables=metadata.referenced_tables,
        schema_slice_hash="schema-v2",
        extractor_hash=metadata.extractor_hash,
        project_config=metadata.project_config,
    )
    changed_project = TaskCacheMetadata(
        sql_hash=metadata.sql_hash,
        referenced_tables=metadata.referenced_tables,
        schema_slice_hash=metadata.schema_slice_hash,
        extractor_hash=metadata.extractor_hash,
        project_config={"catalog": "internal", "db": "other_dm"},
    )

    base_key = task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        metadata=metadata,
    )

    assert base_key == task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        metadata=metadata,
    )
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        metadata=changed_sql,
    )
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        metadata=changed_schema,
    )
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        metadata=changed_project,
    )


def test_task_cache_file_and_result_contract_scenarios(tmp_path):
    cache_path = tmp_path / "task_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {"source_file": "a.sql", "cache_key": "a"},
                    {"source_file": "", "cache_key": "ignored"},
                    {"cache_key": "missing-source"},
                    {"source_file": "b.sql", "cache_key": "b"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_task_cache(cache_path) == {
        "a.sql": {"source_file": "a.sql", "cache_key": "a"},
        "b.sql": {"source_file": "b.sql", "cache_key": "b"},
    }
    assert load_task_cache(tmp_path / "missing.json") == {}
    assert load_task_cache(None) == {}

    result = {
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "missing_ddl_tables": ["missing_table"],
        "missing_source_ddl": ["missing_source"],
        "missing_target_ddl": ["missing_target"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }

    assert cache_entry_from_result(result, "cache-key") == {
        "cache_key": "cache-key",
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "missing_ddl_tables": ["missing_table"],
        "missing_source_ddl": ["missing_source"],
        "missing_target_ddl": ["missing_target"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }


def test_stable_json_hash_is_independent_of_dict_order():
    assert stable_json_hash({"a": 1, "b": 2}) == stable_json_hash(
        {"b": 2, "a": 1}
    )
