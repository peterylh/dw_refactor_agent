import subprocess

import pytest

from dw_refactor_agent.refactor.semantic_mode import (
    automatic_equivalence,
    local_change_fingerprint,
    resolve_semantic_graph,
    resolve_semantic_modes,
    schema_identity_mapping,
    semantic_context_fingerprint,
    sql_ast_equivalent,
)


def _fact(
    name,
    *,
    automatic_mode=None,
    is_direct=False,
    comparable=True,
    local_suffix="v1",
):
    return {
        "table_id": f"id-{name}",
        "local_change_fingerprint": f"sha256:{name}-{local_suffix}",
        "automatic_mode": automatic_mode,
        "is_direct": is_direct,
        "comparable": comparable,
        "evidence": [],
    }


@pytest.mark.parametrize(
    "baseline_sql,current_sql,expected",
    [
        (
            "SELECT id FROM ods_order",
            "-- note\nSELECT  id  FROM ods_order",
            True,
        ),
        (
            "SELECT id FROM ods_order",
            "SELECT id FROM ods_order WHERE id > 0",
            False,
        ),
        ("SELECT * FROM ods_order", "SELECT id FROM ods_order", False),
        (
            "SELECT a.id FROM a JOIN b ON a.id = b.id",
            "SELECT a.id FROM a LEFT JOIN b ON a.id = b.id",
            False,
        ),
        (
            "SELECT id, SUM(v) FROM a GROUP BY id",
            "SELECT id, MAX(v) FROM a GROUP BY id",
            False,
        ),
    ],
)
def test_sql_ast_equivalence_is_strict(baseline_sql, current_sql, expected):
    assert (
        sql_ast_equivalent(baseline_sql, current_sql, rename_mapping={})
        is expected
    )


def test_sql_ast_equivalence_returns_false_for_unparseable_sql():
    assert sql_ast_equivalent("SELECT (", "SELECT (", {}) is False


def test_local_change_fingerprint_is_stable_and_content_sensitive():
    baseline = {
        "logical_name": "dws_sales",
        "ddl": {"path": "mid/ddl/dws_sales.sql", "content_sha256": "a"},
        "task": None,
        "full_refresh_task": None,
        "model": None,
    }
    current = dict(baseline)

    first = local_change_fingerprint("shop", "id-dws-sales", baseline, current)
    second = local_change_fingerprint(
        "shop", "id-dws-sales", dict(reversed(list(baseline.items()))), current
    )
    changed = dict(current)
    changed["task"] = {
        "path": "mid/tasks/dws_sales.sql",
        "content_sha256": "b",
    }

    assert first == second
    assert first != local_change_fingerprint(
        "shop", "id-dws-sales", baseline, changed
    )


def test_context_fingerprint_is_stable_and_tracks_upstream_mode():
    upstream = [
        {
            "upstream_table_id": "id-a",
            "upstream_semantic_context_fingerprint": "sha256:a",
            "upstream_resolved_mode": "equivalent",
        },
        {
            "upstream_table_id": "id-b",
            "upstream_semantic_context_fingerprint": "sha256:b",
            "upstream_resolved_mode": "unknown",
        },
    ]

    first = semantic_context_fingerprint("sha256:local", upstream)
    second = semantic_context_fingerprint(
        "sha256:local", list(reversed(upstream))
    )
    changed = [dict(item) for item in upstream]
    changed[1]["upstream_resolved_mode"] = "equivalent"

    assert first == second
    assert first != semantic_context_fingerprint("sha256:local", changed)


def test_upstream_unknown_overrides_automatic_equivalent():
    result = resolve_semantic_graph(
        {
            "dwd_order": _fact("dwd_order", is_direct=True),
            "dws_sales": _fact("dws_sales", automatic_mode="equivalent"),
        },
        [("dwd_order", "dws_sales")],
    )

    assert result.target_semantics["dwd_order"]["resolved_mode"] == "unknown"
    assert result.target_semantics["dws_sales"]["automatic_mode"] == (
        "equivalent"
    )
    assert result.target_semantics["dws_sales"]["resolved_mode"] == "unknown"
    assert result.target_semantics["dws_sales"]["resolved_source"] == (
        "upstream_propagation"
    )


def test_valid_user_equivalent_overrides_changed_upstream():
    facts = {
        "dwd_order": _fact("dwd_order", is_direct=True),
        "dws_sales": _fact("dws_sales", automatic_mode="equivalent"),
    }
    first = resolve_semantic_graph(facts, [("dwd_order", "dws_sales")])
    upstream_declaration = {
        "table_id": "id-dwd_order",
        "mode": "changed",
        "semantic_context_fingerprint": first.target_semantics["dwd_order"][
            "semantic_context_fingerprint"
        ],
    }
    changed_upstream = resolve_semantic_graph(
        facts,
        [("dwd_order", "dws_sales")],
        current_declarations={"dwd_order": upstream_declaration},
    )
    downstream_declaration = {
        "table_id": "id-dws_sales",
        "mode": "equivalent",
        "semantic_context_fingerprint": changed_upstream.target_semantics[
            "dws_sales"
        ]["semantic_context_fingerprint"],
    }
    result = resolve_semantic_graph(
        facts,
        [("dwd_order", "dws_sales")],
        current_declarations={
            "dwd_order": upstream_declaration,
            "dws_sales": downstream_declaration,
        },
    )

    assert result.target_semantics["dwd_order"]["resolved_mode"] == "changed"
    assert result.target_semantics["dws_sales"]["resolved_mode"] == (
        "equivalent"
    )
    assert result.target_semantics["dws_sales"]["resolved_source"] == "user"


def test_unknown_path_stops_at_nearest_equivalent_boundary():
    facts = {
        "dwd_order": _fact("dwd_order", is_direct=True),
        "dws_sales": _fact("dws_sales"),
        "ads_sales": _fact("ads_sales"),
        "ads_dashboard": _fact("ads_dashboard", automatic_mode="equivalent"),
    }
    edges = [
        ("dwd_order", "dws_sales"),
        ("dws_sales", "ads_sales"),
        ("ads_sales", "ads_dashboard"),
    ]
    first = resolve_semantic_graph(facts, edges)
    declarations = {
        "ads_sales": {
            "table_id": "id-ads_sales",
            "mode": "equivalent",
            "semantic_context_fingerprint": first.target_semantics[
                "ads_sales"
            ]["semantic_context_fingerprint"],
        }
    }

    result = resolve_semantic_graph(
        facts, edges, current_declarations=declarations
    )

    assert result.boundaries == {
        "authority": ["ads_sales"],
        "observational": [],
    }
    assert result.selected_tables == (
        "dwd_order",
        "dws_sales",
        "ads_sales",
    )
    assert "ads_dashboard" not in result.selected_tables


def test_equivalent_direct_table_stops_before_unchanged_downstream():
    facts = {
        "dws_sales": _fact(
            "dws_sales", automatic_mode="equivalent", is_direct=True
        ),
        "ads_sales": _fact("ads_sales", automatic_mode="equivalent"),
    }

    result = resolve_semantic_graph(facts, [("dws_sales", "ads_sales")])

    assert result.boundaries == {
        "authority": ["dws_sales"],
        "observational": [],
    }
    assert result.selected_tables == ("dws_sales",)


def test_independent_direct_descendant_is_selected_below_equivalent_boundary():
    facts = {
        "dws_sales": _fact(
            "dws_sales", automatic_mode="equivalent", is_direct=True
        ),
        "ads_sales": _fact(
            "ads_sales", automatic_mode="equivalent", is_direct=True
        ),
    }

    result = resolve_semantic_graph(facts, [("dws_sales", "ads_sales")])

    assert result.boundaries == {
        "authority": ["ads_sales", "dws_sales"],
        "observational": [],
    }
    assert result.selected_tables == ("dws_sales", "ads_sales")


def test_unknown_leaf_is_observational_and_noncomparable_leaf_is_not():
    comparable = resolve_semantic_graph(
        {"dws_sales": _fact("dws_sales", is_direct=True)}, []
    )
    noncomparable = resolve_semantic_graph(
        {"dws_sales": _fact("dws_sales", is_direct=True, comparable=False)},
        [],
    )

    assert comparable.boundaries["observational"] == ["dws_sales"]
    assert noncomparable.boundaries["observational"] == []
    assert comparable.warnings[0]["type"] == "unknown_table_semantics"


def test_historical_declaration_is_reused_by_table_id_and_context():
    facts = {"dws_sales": _fact("dws_sales", is_direct=True)}
    first = resolve_semantic_graph(facts, [])
    context = first.target_semantics["dws_sales"][
        "semantic_context_fingerprint"
    ]
    history = [
        {
            "run_id": "20260712_100000_shop",
            "verification_intent": {
                "semantic_modes": {
                    "old_dws_sales": {
                        "table_id": "id-dws_sales",
                        "mode": "equivalent",
                        "semantic_context_fingerprint": context,
                        "confirmed_at": "2026-07-12T10:00:00+08:00",
                    }
                }
            },
        }
    ]

    result = resolve_semantic_graph(facts, [], historical_manifests=history)

    record = result.target_semantics["dws_sales"]
    assert record["resolved_mode"] == "equivalent"
    assert record["resolved_source"] == "inherited_user"
    assert (
        result.inherited_declarations["dws_sales"]["inherited_from_run_id"]
        == "20260712_100000_shop"
    )


def test_copied_historical_declaration_keeps_inherited_source():
    facts = {"dws_sales": _fact("dws_sales", is_direct=True)}
    first = resolve_semantic_graph(facts, [])
    declaration = {
        "table_id": "id-dws_sales",
        "mode": "equivalent",
        "semantic_context_fingerprint": first.target_semantics["dws_sales"][
            "semantic_context_fingerprint"
        ],
        "confirmed_at": "2026-07-12T10:00:00+08:00",
        "inherited_from_run_id": "20260712_100000_shop",
    }

    result = resolve_semantic_graph(
        facts,
        [],
        current_declarations={"dws_sales": declaration},
    )

    assert result.target_semantics["dws_sales"]["resolved_source"] == (
        "inherited_user"
    )


def test_stale_current_declaration_is_audited_but_not_applied():
    result = resolve_semantic_graph(
        {"dws_sales": _fact("dws_sales", is_direct=True)},
        [],
        current_declarations={
            "dws_sales": {
                "table_id": "id-dws_sales",
                "mode": "equivalent",
                "semantic_context_fingerprint": "sha256:stale",
            }
        },
    )

    assert result.target_semantics["dws_sales"]["declared_mode"] is None
    assert result.target_semantics["dws_sales"]["resolved_mode"] == "unknown"
    assert {warning["type"] for warning in result.warnings} == {
        "stale_semantic_declaration",
        "unknown_table_semantics",
    }


def test_cycle_is_rejected_before_resolution():
    facts = {"a": _fact("a"), "b": _fact("b")}

    with pytest.raises(ValueError, match="cycle.*a.*b"):
        resolve_semantic_graph(facts, [("a", "b"), ("b", "a")])


TABLE_ID = "e055fdf7-27af-440d-9445-4597f55bf67a"
COLUMN_ID = "89316282-1115-42d8-b953-5c41134e7829"


def _ddl(table_name, column_name, *, table_id=TABLE_ID, column_id=COLUMN_ID):
    return f"""\
-- table_id: {table_id}
CREATE TABLE shop_dm.{table_name} (
    -- column_id: {column_id}
    {column_name} BIGINT NOT NULL
) ENGINE=OLAP
DUPLICATE KEY({column_name})
DISTRIBUTED BY HASH({column_name}) BUCKETS 1;
"""


def _assets(*, ddl, task, model, full_refresh=None):
    return {
        "ddl": ddl,
        "task": task,
        "full_refresh_task": full_refresh,
        "model": model,
    }


def test_schema_identity_mapping_requires_complete_stable_ids():
    mapping = schema_identity_mapping(
        _ddl("dwd_store", "store_id"),
        _ddl("dim_store", "STORE_ID"),
    )
    missing_column_id = schema_identity_mapping(
        _ddl("dwd_store", "store_id", column_id=""),
        _ddl("dim_store", "STORE_ID", column_id=""),
    )

    assert mapping["table_id"] == TABLE_ID
    assert mapping["prod_table"] == "dwd_store"
    assert mapping["qa_table"] == "dim_store"
    assert mapping["column_mapping"] == [
        {
            "column_id": COLUMN_ID,
            "prod": "store_id",
            "qa": "STORE_ID",
        }
    ]
    assert mapping["rename_mapping"] == {
        "dwd_store": "dim_store",
        "store_id": "STORE_ID",
    }
    assert missing_column_id["compare_blocker"].startswith(
        "complete stable column identity"
    )


def test_comment_only_task_change_is_automatically_equivalent():
    baseline = _assets(
        ddl=_ddl("dws_sales", "store_id"),
        task="INSERT INTO dws_sales SELECT store_id FROM ods_store",
        model="version: 2\nname: dws_sales\nlayer: DWS\n",
    )
    current = _assets(
        ddl=_ddl("dws_sales", "store_id"),
        task=(
            "-- explain\nINSERT  INTO dws_sales\n"
            "SELECT store_id FROM ods_store"
        ),
        model="version: 2\nname: dws_sales\nlayer: DWS\n",
    )

    mode, evidence, identity = automatic_equivalence(baseline, current)

    assert mode == "equivalent"
    assert evidence == [{"rule": "normalized_sql_ast_equal"}]
    assert identity["compare_blocker"] is None


@pytest.mark.parametrize(
    "current_task",
    [
        "INSERT INTO dws_sales SELECT store_id FROM ods_store WHERE store_id > 0",
        "INSERT INTO dws_sales SELECT store_id FROM ods_store LEFT JOIN ods_region USING (store_id)",
        "INSERT INTO dws_sales SELECT COUNT(store_id) FROM ods_store",
        "INSERT INTO dws_sales SELECT * FROM ods_store",
    ],
)
def test_semantic_sql_change_is_not_automatically_equivalent(current_task):
    baseline = _assets(
        ddl=_ddl("dws_sales", "store_id"),
        task="INSERT INTO dws_sales SELECT store_id FROM ods_store",
        model="version: 2\nname: dws_sales\nlayer: DWS\n",
    )
    current = _assets(
        ddl=_ddl("dws_sales", "store_id"),
        task=current_task,
        model="version: 2\nname: dws_sales\nlayer: DWS\n",
    )

    assert automatic_equivalence(baseline, current)[0] is None


def test_stable_id_pure_rename_is_automatically_equivalent():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model=(
            "version: 2\nname: dwd_store\nlayer: DWD\n"
            "entities:\n  - code: STORE\n    key_columns:\n      - store_id\n"
        ),
    )
    current = _assets(
        ddl=_ddl("dim_store", "STORE_ID"),
        task="INSERT INTO dim_store SELECT store_id AS STORE_ID FROM ods_store",
        model=(
            "version: 2\nname: dim_store\nlayer: DWD\n"
            "entities:\n  - code: STORE\n    key_columns:\n      - STORE_ID\n"
        ),
    )

    mode, evidence, identity = automatic_equivalence(baseline, current)

    assert mode == "equivalent"
    assert evidence == [{"rule": "stable_id_pure_rename"}]
    assert identity["prod_table"] == "dwd_store"
    assert identity["qa_table"] == "dim_store"


def test_table_rename_does_not_rewrite_qualified_external_source_table():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task=(
            "INSERT INTO shop_dm.dwd_store SELECT store_id FROM ext.dwd_store"
        ),
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )
    current = _assets(
        ddl=_ddl("dim_store", "STORE_ID"),
        task=(
            "INSERT INTO shop_dm.dim_store "
            "SELECT store_id AS STORE_ID FROM ext.dim_store"
        ),
        model="version: 2\nname: dim_store\nlayer: DWD\n",
    )

    assert automatic_equivalence(baseline, current)[0] is None


def test_field_rename_does_not_rewrite_unqualified_source_expression():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )
    current = _assets(
        ddl=_ddl("dwd_store", "renamed_store_id"),
        task=("INSERT INTO dwd_store SELECT renamed_store_id FROM ods_store"),
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )

    assert automatic_equivalence(baseline, current)[0] is None


def test_field_rename_with_explicit_output_alias_is_automatic():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )
    current = _assets(
        ddl=_ddl("dwd_store", "renamed_store_id"),
        task=(
            "INSERT INTO dwd_store "
            "SELECT store_id AS renamed_store_id FROM ods_store"
        ),
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )

    assert automatic_equivalence(baseline, current)[0] == "equivalent"


def test_field_rename_does_not_rewrite_arbitrary_model_semantics():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model=(
            "version: 2\nname: dwd_store\nlayer: DWD\ndescription: store_id\n"
        ),
    )
    current = _assets(
        ddl=_ddl("dwd_store", "renamed_store_id"),
        task=(
            "INSERT INTO dwd_store "
            "SELECT store_id AS renamed_store_id FROM ods_store"
        ),
        model=(
            "version: 2\nname: dwd_store\nlayer: DWD\n"
            "description: renamed_store_id\n"
        ),
    )

    assert automatic_equivalence(baseline, current)[0] is None


def test_table_rename_collision_with_column_identity_is_not_automatic():
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )
    current = _assets(
        ddl=_ddl("store_id", "store_id"),
        task="INSERT INTO store_id SELECT dwd_store FROM ods_store",
        model="version: 2\nname: store_id\nlayer: DWD\n",
    )

    assert automatic_equivalence(baseline, current)[0] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "version: 2\nname: dim_store\nlayer: DIM\n"),
        (
            "ddl",
            _ddl("dim_store", "STORE_ID").replace(
                "BIGINT NOT NULL", "VARCHAR(20) NOT NULL"
            ),
        ),
        (
            "task",
            "INSERT INTO dim_store SELECT store_id + 1 AS STORE_ID FROM ods_store",
        ),
    ],
)
def test_rename_with_nonrename_semantic_change_is_not_equivalent(field, value):
    baseline = _assets(
        ddl=_ddl("dwd_store", "store_id"),
        task="INSERT INTO dwd_store SELECT store_id FROM ods_store",
        model="version: 2\nname: dwd_store\nlayer: DWD\n",
    )
    current = _assets(
        ddl=_ddl("dim_store", "STORE_ID"),
        task="INSERT INTO dim_store SELECT store_id AS STORE_ID FROM ods_store",
        model="version: 2\nname: dim_store\nlayer: DWD\n",
    )
    current[field] = value

    assert automatic_equivalence(baseline, current)[0] is None


def _git(root, *args):
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_semantic_table(root, table, ddl, task):
    ddl_path = root / "warehouses/shop/mid/ddl" / f"{table}.sql"
    task_path = root / "warehouses/shop/mid/tasks" / f"{table}.sql"
    ddl_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.parent.mkdir(parents=True, exist_ok=True)
    ddl_path.write_text(ddl, encoding="utf-8")
    task_path.write_text(task, encoding="utf-8")
    return task_path


def _lineage(*edges):
    return {
        "edges": [
            {
                "source": {"type": "column", "id": f"{source}.id"},
                "target": {"type": "column", "id": f"{target}.id"},
            }
            for source, target in edges
        ]
    }


def _change_analysis(direct, downstream=()):
    return {
        "changed_assets": {
            "ddl_tables": [],
            "task_jobs": list(direct),
            "model_tables": [],
            "config_files": [],
        },
        "affected_scope": {
            "direct_tables": list(direct),
            "downstream_tables": list(downstream),
            "anchor_tables": list(downstream),
        },
    }


def _semantic_git_project(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    dws_task = _write_semantic_table(
        tmp_path,
        "dws_sales",
        _ddl("dws_sales", "store_id"),
        "INSERT INTO dws_sales SELECT store_id FROM ods_store;\n",
    )
    ads_task = _write_semantic_table(
        tmp_path,
        "ads_sales",
        _ddl(
            "ads_sales",
            "store_id",
            table_id="6c60fd39-fb02-4124-8477-3cf173896d90",
            column_id="6d346393-0b41-42af-9079-c788039f5d9c",
        ),
        "INSERT INTO ads_sales SELECT store_id FROM dws_sales;\n",
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "baseline")
    return _git(tmp_path, "rev-parse", "HEAD"), dws_task, ads_task


def test_resolve_semantic_modes_reads_git_and_worktree_assets(tmp_path):
    base_ref, dws_task, _ads_task = _semantic_git_project(tmp_path)
    dws_task.write_text(
        "-- formatting only\nINSERT  INTO dws_sales "
        "SELECT store_id FROM ods_store;\n",
        encoding="utf-8",
    )

    result = resolve_semantic_modes(
        project="shop",
        project_dir="warehouses/shop",
        change_analysis=_change_analysis(["dws_sales"]),
        baseline_lineage=_lineage(),
        current_lineage=_lineage(),
        base_ref=base_ref,
        repo_root=tmp_path,
        current_manifest={"verification_intent": {"semantic_modes": {}}},
        historical_manifests=[],
    )

    semantics = result.target_semantics["dws_sales"]
    assert semantics["automatic_mode"] == "equivalent"
    assert semantics["resolved_mode"] == "equivalent"
    assert semantics["table_id"] == TABLE_ID
    assert result.selected_tables == ("dws_sales",)
    assert result.boundaries["authority"] == ["dws_sales"]


def test_resolve_semantic_modes_keeps_filter_change_unknown_to_leaf(tmp_path):
    base_ref, dws_task, _ads_task = _semantic_git_project(tmp_path)
    dws_task.write_text(
        "INSERT INTO dws_sales SELECT store_id FROM ods_store "
        "WHERE store_id > 0;\n",
        encoding="utf-8",
    )
    lineage = _lineage(("dws_sales", "ads_sales"))

    result = resolve_semantic_modes(
        project="shop",
        project_dir="warehouses/shop",
        change_analysis=_change_analysis(["dws_sales"], ["ads_sales"]),
        baseline_lineage=lineage,
        current_lineage=lineage,
        base_ref=base_ref,
        repo_root=tmp_path,
        current_manifest={"verification_intent": {"semantic_modes": {}}},
        historical_manifests=[],
    )

    assert result.target_semantics["dws_sales"]["automatic_mode"] is None
    assert result.target_semantics["dws_sales"]["resolved_mode"] == "unknown"
    assert result.target_semantics["ads_sales"]["automatic_mode"] == (
        "equivalent"
    )
    assert result.target_semantics["ads_sales"]["resolved_source"] == (
        "upstream_propagation"
    )
    assert result.selected_tables == ("dws_sales", "ads_sales")
    assert result.boundaries["observational"] == ["ads_sales"]
