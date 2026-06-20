from __future__ import annotations

import json

from lineage.task_cache import (
    cache_entry_from_result,
    load_task_cache,
    stable_json_hash,
    task_cache_key,
)


def test_task_cache_key_changes_when_sql_schema_or_project_config_changes():
    schema = {
        "internal": {
            "demo_dm": {
                "ods_order": {"order_id": "BIGINT", "amount": "DECIMAL"},
                "dwd_order": {"order_id": "BIGINT", "amount": "DECIMAL"},
            }
        }
    }
    sql = """
    INSERT INTO demo_dm.dwd_order
    SELECT order_id, amount FROM demo_dm.ods_order
    """

    base_key = task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        sql_text=sql,
        schema=schema,
        project_config={"catalog": "internal", "db": "demo_dm"},
        extractor_hash="extractor-v1",
    )

    assert base_key == task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        sql_text=sql,
        schema=schema,
        project_config={"db": "demo_dm", "catalog": "internal"},
        extractor_hash="extractor-v1",
    )
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        sql_text=sql.replace("amount", "net_amount"),
        schema=schema,
        project_config={"catalog": "internal", "db": "demo_dm"},
        extractor_hash="extractor-v1",
    )
    changed_schema = {
        "internal": {
            "demo_dm": {
                "ods_order": {
                    "order_id": "BIGINT",
                    "amount": "DECIMAL",
                    "status": "VARCHAR",
                },
                "dwd_order": {"order_id": "BIGINT", "amount": "DECIMAL"},
            }
        }
    }
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        sql_text=sql,
        schema=changed_schema,
        project_config={"catalog": "internal", "db": "demo_dm"},
        extractor_hash="extractor-v1",
    )
    assert base_key != task_cache_key(
        project="demo",
        source_file="dwd_order.sql",
        sql_text=sql,
        schema=schema,
        project_config={"catalog": "internal", "db": "other_dm"},
        extractor_hash="extractor-v1",
    )


def test_load_task_cache_indexes_valid_entries_by_source_file(tmp_path):
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


def test_cache_entry_from_result_preserves_reusable_task_result_fields():
    result = {
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "missing_ddl_tables": ["missing_table"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }

    assert cache_entry_from_result(result, "cache-key") == {
        "cache_key": "cache-key",
        "source_file": "dwd_order.sql",
        "entries": [{"target": "demo_dm.dwd_order"}],
        "transient_tables": ["tmp_order"],
        "missing_ddl_tables": ["missing_table"],
        "stats": {"entry_count": 1},
        "errors": [{"message": "warn"}],
    }


def test_stable_json_hash_is_independent_of_dict_order():
    assert stable_json_hash({"a": 1, "b": 2}) == stable_json_hash(
        {"b": 2, "a": 1}
    )
