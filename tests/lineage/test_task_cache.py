from __future__ import annotations

import inspect
import json

import dw_refactor_agent.lineage.task_cache as task_cache
from dw_refactor_agent.lineage.task_cache import (
    TaskCacheMetadata,
    cache_entry_from_result,
    extractor_version_hash,
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
                "format_version": 2,
                "tasks": [
                    {
                        "source_file": "a.sql",
                        "cache_key": "a",
                        "input_tables": [],
                        "output_tables": [],
                        "created_tables": [],
                        "temporary_tables": [],
                        "local_lifecycle_tables": [],
                    },
                    {"source_file": "", "cache_key": "ignored"},
                    {"cache_key": "missing-source"},
                    {"source_file": "b.sql", "cache_key": "b"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_task_cache(cache_path) == {
        "a.sql": {
            "source_file": "a.sql",
            "cache_key": "a",
            "input_tables": [],
            "output_tables": [],
            "created_tables": [],
            "temporary_tables": [],
            "local_lifecycle_tables": [],
        },
    }
    assert load_task_cache(tmp_path / "missing.json") == {}
    assert load_task_cache(None) == {}

    result = {
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "input_tables": ["demo_dm.ods_order"],
        "output_tables": ["demo_dm.dwd_order"],
        "created_tables": [],
        "temporary_tables": [],
        "local_lifecycle_tables": [],
        "missing_ddl_tables": ["missing_table"],
        "missing_source_ddl": ["missing_source"],
        "missing_target_ddl": ["missing_target"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }
    assert cache_entry_from_result(result, "cache-key") == {
        "format_version": 2,
        "cache_key": "cache-key",
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "input_tables": ["demo_dm.ods_order"],
        "output_tables": ["demo_dm.dwd_order"],
        "created_tables": [],
        "temporary_tables": [],
        "local_lifecycle_tables": [],
        "missing_ddl_tables": ["missing_table"],
        "missing_source_ddl": ["missing_source"],
        "missing_target_ddl": ["missing_target"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }


def test_load_task_cache_rejects_unversioned_fact_schema(tmp_path):
    cache_path = tmp_path / "legacy_task_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "source_file": "legacy.sql",
                        "cache_key": "legacy",
                        "input_tables": [],
                        "output_tables": [],
                        "created_tables": [],
                        "temporary_tables": [],
                        "local_lifecycle_tables": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert load_task_cache(cache_path) == {}


def test_versioned_cache_entry_survives_unversioned_container(tmp_path):
    cache_path = tmp_path / "incremental_task_cache.json"
    entry = cache_entry_from_result(
        {
            "source_file": "incremental.sql",
            "input_tables": [],
            "output_tables": [],
            "created_tables": [],
            "temporary_tables": [],
            "local_lifecycle_tables": [],
        },
        "cache-key",
    )
    cache_path.write_text(
        json.dumps({"tasks": [entry]}),
        encoding="utf-8",
    )

    assert load_task_cache(cache_path) == {"incremental.sql": entry}


def test_cache_entry_sorts_set_facts_for_json_serialization():
    entry = cache_entry_from_result(
        {
            "source_file": "prepare.sql",
            "input_tables": {"b", "a"},
            "output_tables": {"out"},
            "created_tables": {"out"},
            "temporary_tables": set(),
            "local_lifecycle_tables": [],
        },
        "cache-key",
    )

    assert entry["input_tables"] == ["a", "b"]
    json.dumps(entry)


def test_stable_json_hash_is_independent_of_dict_order():
    assert stable_json_hash({"a": 1, "b": 2}) == stable_json_hash(
        {"b": 2, "a": 1}
    )


def test_extractor_version_hash_covers_task_fact_implementation(tmp_path):
    extractor_file = tmp_path / "lineage_extractor.py"
    facts_file = tmp_path / "sql_task_facts.py"
    extractor_file.write_text("extractor-v1", encoding="utf-8")
    facts_file.write_text("facts-v1", encoding="utf-8")

    before = extractor_version_hash((extractor_file, facts_file))
    facts_file.write_text("facts-v2", encoding="utf-8")

    assert extractor_version_hash((extractor_file, facts_file)) != before
