import threading
from dataclasses import FrozenInstanceError

import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.model_generation_manifest import (
    _json_hash,
    build_generate_asset_preflight,
    revalidate_generate_asset_manifest,
)
from dw_refactor_agent.assessment.llm.model_metadata_catalog import (
    update_model_yaml_from_catalog,
)
from dw_refactor_agent.assessment.llm.model_metadata_generation import (
    plan_generate_model_metadata,
)
from dw_refactor_agent.assessment.llm.model_metadata_publication import (
    metadata_publication_lock,
)
from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    run_generate_model_metadata,
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    load_business_semantics_catalog,
    write_initial_business_semantics_catalog,
)
from tests.assess.model_metadata_writer_test_support import (
    _catalog_payload,
    _configure_project_root,
    _write_split_catalog,
)


def _configure_project(tmp_path, monkeypatch, project):
    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    (project_dir / "mid" / "tasks").mkdir(parents=True)
    _write_split_catalog(project_dir, project, _catalog_payload())
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "catalog": "internal", "db": "demo"},
    )
    return project_dir


def _write_managed_table(project_dir, table_name="dwd_orders"):
    ddl_path = project_dir / "mid" / "ddl" / f"{table_name}.sql"
    task_path = project_dir / "mid" / "tasks" / f"{table_name}.sql"
    ddl_path.write_text(
        f"CREATE TABLE demo.{table_name} (id BIGINT, stat_date DATE);\n",
        encoding="utf-8",
    )
    task_path.write_text(
        f"TRUNCATE TABLE demo.{table_name};\n"
        f"INSERT INTO demo.{table_name} SELECT 1, CURRENT_DATE;\n",
        encoding="utf-8",
    )
    return ddl_path, task_path


def _error_types(preflight):
    return {error["type"] for error in preflight.errors}


def _write_config_source(tmp_path, monkeypatch, project, *, database="demo"):
    path = tmp_path / "warehouses" / "config_holder" / "warehouse.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"name: {project}\n"
        f"dir: ../../{project}\n"
        "catalog: internal\n"
        f"db: {database}\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        config.load_warehouse_config(path, tmp_path),
    )
    return path


def _revalidate(
    preflight,
    catalog,
    *,
    names=("dwd_orders",),
    declared=(("dwd_orders", "dwd_orders"),),
    paths=None,
):
    if paths is None:
        paths = [
            config.core.PROJECT_ROOT / path
            for path in preflight.manifest.expected_model_paths
        ]
    return revalidate_generate_asset_manifest(
        preflight.manifest,
        catalog=catalog,
        candidate_table_names=names,
        candidate_declared_names=declared,
        rendered_model_paths=paths,
    )


def test_manifest_is_immutable_and_frozen_inputs_drive_candidate(
    tmp_path,
    monkeypatch,
):
    project = "manifest_snapshot"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    ddl_path, task_path = _write_managed_table(project_dir)
    model_path = project_dir / "mid" / "models" / "dwd_orders.yaml"
    model_path.parent.mkdir(parents=True)
    model_path.write_text(
        "version: 2\nname: dwd_orders\nlayer: ADS\n",
        encoding="utf-8",
    )
    catalog = _catalog_payload()
    first = build_generate_asset_preflight(project, catalog)
    first_plan = plan_generate_model_metadata(
        project,
        catalog,
        replace_existing_models=True,
        write_scope="all",
        asset_manifest=first.manifest,
    )

    assert first.passed
    assert first.manifest.inspection_target_set == (
        "internal.demo.dwd_orders",
    )
    assert first.manifest.existing_model_paths == (
        f"{project}/mid/models/dwd_orders.yaml",
    )
    asset = first.manifest.assets[0]
    for fingerprint in (
        first.manifest.catalog_snapshot_hash,
        first.manifest.base_formal_files_hash,
        first.manifest.manifest_hash,
        asset.ddl_content_hash,
        *asset.task_content_hashes,
    ):
        assert fingerprint.startswith("sha256:")
    assert set(asset.to_dict()) == {
        "canonical_identity",
        "display_identity",
        "short_name",
        "asset_role",
        "operational_layer",
        "ddl_path",
        "ddl_content_hash",
        "task_paths",
        "task_content_hashes",
        "target_model_path",
        "existing_target_hash",
        "producer_mode",
        "producer_reason",
        "execution_contract",
        "execution_evidence_hash",
        "lineage_evidence_hash",
        "inspection_target",
        "managed",
    }
    assert first.manifest.to_dict()["assets"] == [asset.to_dict()]
    assert asset.canonical_identity == "internal.demo.dwd_orders"
    assert asset.producer_mode == "task"
    assert asset.execution_contract() == {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }
    assert asset.inspection_content()["ddl"] == ddl_path.read_text(
        encoding="utf-8"
    )
    assert asset.validation_asset()["tasks"][0]["sql"] == task_path.read_text(
        encoding="utf-8"
    )
    with pytest.raises(FrozenInstanceError):
        first.manifest.project = "changed"

    task_path.write_text(
        "TRUNCATE TABLE demo.dwd_orders;\n"
        "INSERT INTO demo.dwd_orders SELECT 2, CURRENT_DATE;\n",
        encoding="utf-8",
    )
    assert _error_types(_revalidate(first, catalog)) == {
        "asset_manifest_changed"
    }
    ddl_path.write_text(
        "CREATE TABLE demo.dwd_orders (changed VARCHAR(10));\n",
        encoding="utf-8",
    )
    frozen_plan = plan_generate_model_metadata(
        project,
        {"version": 999, "project_context": "outside manifest"},
        replace_existing_models=True,
        write_scope="all",
        asset_manifest=first.manifest,
    )
    assert frozen_plan.model_metadata == first_plan.model_metadata
    assert "asset_manifest_changed" in _error_types(
        _revalidate(first, catalog)
    )

    _write_managed_table(project_dir)
    model_path.write_text(
        "version: 2\nname: dwd_orders\nlayer: DIM\n"
        "semantic_subject: SHOULD_NOT_BE_A_PRIOR\n",
        encoding="utf-8",
    )
    second = build_generate_asset_preflight(project, catalog)
    second_plan = plan_generate_model_metadata(
        project,
        catalog,
        replace_existing_models=True,
        write_scope="all",
        asset_manifest=second.manifest,
    )
    assert first.manifest.base_formal_files_hash != (
        second.manifest.base_formal_files_hash
    )
    assert first_plan.model_metadata == second_plan.model_metadata
    assert second_plan.model_metadata["dwd_orders"]["layer"] == "DWD"


def test_external_taskless_ddl_only_table_can_complete_cold_start(
    tmp_path,
    monkeypatch,
):
    project = "manifest_external_taskless"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    ddl_path = project_dir / "mid" / "ddl" / "dim_currency.sql"
    ddl_path.write_text(
        "CREATE TABLE demo.dim_currency (currency_code VARCHAR(3));\n",
        encoding="utf-8",
    )
    config.PROJECT_CONFIG[project]["execution"] = {
        "taskless_assets": [
            {
                "table": "internal.demo.dim_currency",
                "producer": "external",
                "reason": "maintained_by_reference_data_sync",
            }
        ]
    }

    preflight = build_generate_asset_preflight(project, _catalog_payload())
    plan = plan_generate_model_metadata(
        project,
        _catalog_payload(),
        replace_existing_models=True,
        write_scope="all",
        asset_manifest=preflight.manifest,
    )
    result = run_generate_model_metadata(project, dry_run=False)
    saved = yaml.safe_load(
        (project_dir / "mid" / "models" / "dim_currency.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert preflight.passed
    asset = preflight.manifest.assets[0]
    assert asset.producer_mode == "external"
    assert asset.producer_reason == "maintained_by_reference_data_sync"
    assert asset.execution_contract() == {"mode": "taskless"}
    assert preflight.manifest.to_dict()["taskless_tables"] == [
        {
            "canonical_identity": "internal.demo.dim_currency",
            "display_identity": "internal.demo.dim_currency",
            "producer": "external",
            "reason": "maintained_by_reference_data_sync",
        }
    ]
    assert plan.model_metadata["dim_currency"]["execution"] == {
        "mode": "taskless"
    }
    assert result["publication"]["status"] == "published_with_quarantine"
    assert saved["execution"] == {"mode": "taskless"}


@pytest.mark.parametrize(
    "taskless_assets,error_type",
    [
        ({}, "taskless_asset_config_invalid"),
        (
            [
                {
                    "table": "dim_currency",
                    "producer": "external",
                    "reason": "sync",
                }
            ],
            "taskless_asset_config_invalid",
        ),
        (
            [
                {
                    "table": "internal.demo.unknown_table",
                    "producer": "external",
                    "reason": "sync",
                }
            ],
            "taskless_asset_missing_ddl",
        ),
    ],
)
def test_external_taskless_declaration_fails_closed(
    tmp_path,
    monkeypatch,
    taskless_assets,
    error_type,
):
    project = "manifest_external_invalid"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    (project_dir / "mid" / "ddl" / "dim_currency.sql").write_text(
        "CREATE TABLE demo.dim_currency (currency_code VARCHAR(3));\n",
        encoding="utf-8",
    )
    config.PROJECT_CONFIG[project]["execution"] = {
        "taskless_assets": taskless_assets
    }

    preflight = build_generate_asset_preflight(project, _catalog_payload())

    assert not preflight.passed
    assert error_type in _error_types(preflight)


def test_external_taskless_declaration_rejects_task_binding(
    tmp_path,
    monkeypatch,
):
    project = "manifest_external_task_conflict"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _write_managed_table(project_dir, "dim_currency")
    config.PROJECT_CONFIG[project]["execution"] = {
        "taskless_assets": [
            {
                "table": "internal.demo.dim_currency",
                "producer": "external",
                "reason": "sync",
            }
        ]
    }

    preflight = build_generate_asset_preflight(project, _catalog_payload())

    assert not preflight.passed
    assert "execution_task_binding_conflict" in _error_types(preflight)


def test_taskless_declaration_does_not_allow_orphan_full_refresh_task(
    tmp_path,
    monkeypatch,
):
    project = "manifest_external_orphan_companion"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    (project_dir / "mid" / "ddl" / "dim_currency.sql").write_text(
        "CREATE TABLE demo.dim_currency (currency_code VARCHAR(3));\n",
        encoding="utf-8",
    )
    full_refresh_dir = project_dir / "mid" / "tasks" / "full_refresh"
    full_refresh_dir.mkdir()
    (full_refresh_dir / "dim_currency_full_refresh.sql").write_text(
        "INSERT INTO demo.dim_currency SELECT 'CNY';\n",
        encoding="utf-8",
    )
    config.PROJECT_CONFIG[project]["execution"] = {
        "taskless_assets": [
            {
                "table": "internal.demo.dim_currency",
                "producer": "external",
                "reason": "sync",
            }
        ]
    }

    preflight = build_generate_asset_preflight(project, _catalog_payload())

    assert not preflight.passed
    assert {
        "execution_main_task_missing",
        "execution_task_binding_conflict",
    }.issubset(_error_types(preflight))


def test_generate_returns_structured_block_for_inspection_target_mismatch(
    tmp_path,
    monkeypatch,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module
    from dw_refactor_agent.assessment.llm.context_builder import (
        InspectionContextSetError,
    )

    project = "manifest_external_context_mismatch"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    (project_dir / "mid" / "ddl" / "dim_currency.sql").write_text(
        "CREATE TABLE demo.dim_currency (currency_code VARCHAR(3));\n",
        encoding="utf-8",
    )
    config.PROJECT_CONFIG[project]["execution"] = {
        "taskless_assets": [
            {
                "table": "internal.demo.dim_currency",
                "producer": "external",
                "reason": "sync",
            }
        ]
    }

    def mismatched_context(*_args, **_kwargs):
        raise InspectionContextSetError(
            "inspection_context_set_mismatch: missing dim_currency",
            expected=["internal.demo.dim_currency"],
        )

    monkeypatch.setattr(
        writer_module, "run_metadata_write", mismatched_context
    )

    result = run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=True,
    )

    assert result["publication"]["candidate_status"] == "blocked"
    assert result["publication"]["validation"]["errors"] == [
        {
            "type": "inspection_context_set_mismatch",
            "table": "",
            "message": (
                "inspection_context_set_mismatch: missing dim_currency"
            ),
        }
    ]


def test_preflight_uses_current_sql_for_transient_and_stale_lineage(
    tmp_path,
    monkeypatch,
):
    project = "manifest_dataset_types"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _ddl_path, task_path = _write_managed_table(project_dir)
    task_path.write_text(
        "CREATE TABLE demo.process_stage AS SELECT 1 AS id;\n"
        "CREATE TEMPORARY TABLE demo.temp_stage (id BIGINT);\n"
        "TRUNCATE TABLE demo.dwd_orders;\n"
        "INSERT INTO demo.dwd_orders SELECT id, CURRENT_DATE "
        "FROM demo.process_stage;\n",
        encoding="utf-8",
    )
    orphan_task = project_dir / "mid" / "tasks" / "orphan.sql"
    orphan_task.write_text(
        "INSERT INTO demo.dwd_orphan SELECT 1;\n",
        encoding="utf-8",
    )
    lineage_path = project_dir / "artifacts" / "lineage" / "lineage_data.json"
    lineage_path.parent.mkdir(parents=True)
    lineage_path.write_text(
        '{"tables":[{"name":"demo.dwd_orphan","dataset_type":"process"}]}',
        encoding="utf-8",
    )

    first = build_generate_asset_preflight(project, _catalog_payload())

    assert _error_types(first) == {"task_target_missing_ddl"}
    assert {
        item.canonical_identity: item.dataset_type
        for item in first.manifest.excluded_datasets
    } == {
        "internal.demo.process_stage": "process",
        "internal.demo.temp_stage": "temporary",
    }
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer

    monkeypatch.setattr(
        writer,
        "run_metadata_write",
        lambda *_args, **_kwargs: pytest.fail("LLM called before preflight"),
    )
    blocked = run_generate_model_metadata(project, api_key="unused")
    assert blocked["publication"]["status"] == "blocked"
    assert blocked["checkpoint"]["status"] == "not_started"

    orphan_task.unlink()
    task_path.write_text(
        "DELETE FROM demo.dwd_orders WHERE stat_date = @etl_date;\n"
        "INSERT INTO demo.dwd_orders SELECT 1, @etl_date;\n",
        encoding="utf-8",
    )
    lineage_path.write_text(
        '{"tables":[{"name":"demo.dwd_orders","dataset_type":"process"}]}',
        encoding="utf-8",
    )
    second = build_generate_asset_preflight(project, _catalog_payload())
    assert second.passed
    assert second.manifest.excluded_datasets == ()


def test_preflight_blocks_identity_and_casefold_path_collisions(
    tmp_path,
    monkeypatch,
):
    project = "manifest_collisions"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    ads_ddl = project_dir / "ads" / "ddl"
    ads_ddl.mkdir(parents=True)
    for path, sql in (
        (
            project_dir / "mid" / "ddl" / "sales.sql",
            "CREATE TABLE demo.sales (id BIGINT);\n",
        ),
        (
            ads_ddl / "SALES.sql",
            "CREATE TABLE DEMO.SALES (id BIGINT);\n",
        ),
        (
            project_dir / "mid" / "ddl" / "sales_a_one.sql",
            "CREATE TABLE db_a.sales_a (id BIGINT);\n",
        ),
        (
            project_dir / "mid" / "ddl" / "sales_a_two.sql",
            "CREATE TABLE db_b.SALES_A (id BIGINT);\n",
        ),
    ):
        path.write_text(sql, encoding="utf-8")

    preflight = build_generate_asset_preflight(project, _catalog_payload())

    assert {
        "ddl_identity_conflict",
        "model_key_conflict",
        "model_path_conflict",
    } <= _error_types(preflight)


def test_ods_identity_comes_from_directories_and_rejects_qualifier_mismatch(
    tmp_path,
    monkeypatch,
):
    project = "manifest_ods_identity"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    for catalog in ("source_a", "source_b"):
        ddl_dir = project_dir / "ods" / "ddl" / catalog / "raw"
        ddl_dir.mkdir(parents=True)
        (ddl_dir / "orders.sql").write_text(
            "CREATE TABLE orders (id BIGINT);\n",
            encoding="utf-8",
        )

    first = build_generate_asset_preflight(project, _catalog_payload())
    assert {asset.canonical_identity for asset in first.manifest.assets} == {
        "source_a.raw.orders",
        "source_b.raw.orders",
    }
    assert _error_types(first) == {"model_key_conflict"}

    ddl_dir = project_dir / "ods" / "ddl" / "source_c" / "raw"
    task_dir = project_dir / "ods" / "tasks" / "source_c" / "raw"
    ddl_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (ddl_dir / "mismatch.sql").write_text(
        "CREATE TABLE other.raw.mismatch (id BIGINT);\n",
        encoding="utf-8",
    )
    (task_dir / "mismatch.sql").write_text(
        "INSERT INTO other.raw.mismatch SELECT 1;\n",
        encoding="utf-8",
    )
    assert {
        "ddl_identity_directory_mismatch",
        "task_identity_directory_mismatch",
    } <= _error_types(
        build_generate_asset_preflight(project, _catalog_payload())
    )


@pytest.mark.parametrize(
    ("names", "declared", "rendered_names", "expected"),
    [
        (
            ("dwd_orders", "DWD_ORDERS"),
            (("dwd_orders", "dwd_orders"), ("DWD_ORDERS", "DWD_ORDERS")),
            ("dwd_orders.yaml", "DWD_ORDERS.yaml"),
            {
                "candidate_model_identity_changed",
                "candidate_model_set_changed",
                "expected_model_set_changed",
            },
        ),
        (
            ("dwd_orders",),
            (("dwd_orders", "another_table"),),
            ("dwd_orders.yaml",),
            {"candidate_model_identity_changed"},
        ),
        (
            (),
            (),
            (),
            {
                "candidate_model_identity_changed",
                "candidate_model_set_changed",
                "expected_model_set_changed",
            },
        ),
    ],
)
def test_revalidation_rejects_candidate_set_and_yaml_identity_changes(
    tmp_path,
    monkeypatch,
    names,
    declared,
    rendered_names,
    expected,
):
    project = "manifest_candidate_identity"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _write_managed_table(project_dir)
    catalog = _catalog_payload()
    preflight = build_generate_asset_preflight(project, catalog)
    model_dir = project_dir / "mid" / "models"
    paths = [model_dir / path_name for path_name in rendered_names]

    changed = _revalidate(
        preflight,
        catalog,
        names=names,
        declared=declared,
        paths=paths,
    )
    assert _error_types(changed) == expected


@pytest.mark.parametrize("mutation", ["lineage_deleted", "config_changed"])
def test_revalidation_detects_external_input_changes(
    tmp_path,
    monkeypatch,
    mutation,
):
    project = f"manifest_revalidate_{mutation}"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _write_managed_table(project_dir)
    lineage_path = project_dir / "artifacts" / "lineage" / "lineage_data.json"
    lineage_path.parent.mkdir(parents=True)
    lineage_path.write_text(
        '{"tables":[{"name":"demo.dwd_orders"}],"edges":[]}',
        encoding="utf-8",
    )
    config_path = _write_config_source(tmp_path, monkeypatch, project)
    catalog = _catalog_payload()
    preflight = build_generate_asset_preflight(project, catalog)

    if mutation == "lineage_deleted":
        lineage_path.unlink()
        expected = {"asset_manifest_changed"}
    else:
        config_path.write_text(
            config_path.read_text(encoding="utf-8").replace(
                "db: demo", "db: changed"
            ),
            encoding="utf-8",
        )
        expected = {"asset_manifest_changed", "project_config_stale"}

    assert _error_types(_revalidate(preflight, catalog)) == expected


@pytest.mark.parametrize(
    ("source_state", "expected_error"),
    [
        ("stale", "project_config_stale"),
        ("missing", "project_config_source_missing"),
        ("invalid", "project_config_source_invalid"),
    ],
)
def test_preflight_fails_closed_for_unusable_cached_config(
    tmp_path,
    monkeypatch,
    source_state,
    expected_error,
):
    project = f"manifest_config_{source_state}"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _write_managed_table(project_dir)
    path = _write_config_source(tmp_path, monkeypatch, project)
    if source_state == "stale":
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "db: demo", "db: changed"
            ),
            encoding="utf-8",
        )
    elif source_state == "missing":
        path.unlink()
    else:
        path.write_text("name: [unterminated\n", encoding="utf-8")

    preflight = build_generate_asset_preflight(project, _catalog_payload())

    assert _error_types(preflight) == {expected_error}


def test_shared_publication_lock_covers_catalog_and_model_writers(
    tmp_path,
    monkeypatch,
):
    project = "manifest_shared_lock"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    started = [threading.Event(), threading.Event()]
    finished = [threading.Event(), threading.Event()]

    def catalog_writer():
        started[0].set()
        write_initial_business_semantics_catalog(
            project,
            overwrite=True,
            dry_run=False,
        )
        finished[0].set()

    def model_writer():
        started[1].set()
        update_model_yaml_from_catalog(
            project,
            "dwd_orders",
            {"layer": "DWD", "table_type": "fact"},
            dry_run=False,
        )
        finished[1].set()

    threads = [
        threading.Thread(target=catalog_writer),
        threading.Thread(target=model_writer),
    ]
    with metadata_publication_lock(project):
        for thread in threads:
            thread.start()
        assert all(event.wait(2) for event in started)
        assert not any(event.wait(0.1) for event in finished)

    assert all(event.wait(2) for event in finished)
    for thread in threads:
        thread.join(timeout=2)
        assert not thread.is_alive()
    assert (project_dir / "mid" / "models" / "dwd_orders.yaml").exists()


def test_generate_refreshes_stale_catalog_cache_before_snapshot(
    tmp_path,
    monkeypatch,
):
    project = "manifest_catalog_cache"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    _write_managed_table(project_dir)
    cached = load_business_semantics_catalog(project)
    old_hash = _json_hash(cached)
    taxonomy_path = project_dir / "business_taxonomy.yaml"
    taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    taxonomy["project_context"] = "fresh formal context"
    taxonomy_path.write_text(
        yaml.safe_dump(taxonomy, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    stale = build_generate_asset_preflight(project, cached)
    result = run_generate_model_metadata(project, dry_run=True)

    assert _error_types(stale) == {"catalog_snapshot_stale"}
    assert result["publication"]["status"] == "dry_run"
    assert result["asset_manifest"]["catalog_snapshot_hash"] != old_hash


def test_generate_deletes_frozen_nondefault_ods_orphan_model(
    tmp_path,
    monkeypatch,
):
    project = "manifest_frozen_delete"
    project_dir = _configure_project(tmp_path, monkeypatch, project)
    ddl_dir = project_dir / "ods" / "ddl" / "vendor" / "raw"
    ddl_dir.mkdir(parents=True)
    (ddl_dir / "orders.sql").write_text(
        "CREATE TABLE orders (id BIGINT);\n",
        encoding="utf-8",
    )
    orphan = (
        project_dir
        / "ods"
        / "models"
        / "legacy_vendor"
        / "legacy_raw"
        / "orphan.yaml"
    )
    orphan.parent.mkdir(parents=True)
    orphan.write_text(
        "version: 2\nname: orphan\nlayer: ODS\n",
        encoding="utf-8",
    )

    result = run_generate_model_metadata(
        project,
        dry_run=False,
        update_catalog=False,
    )

    assert result["publication"]["status"] == "published"
    assert str(orphan) in result["planned_deleted_model_files"]
    assert not orphan.exists()
    assert (
        project_dir / "ods" / "models" / "vendor" / "raw" / "orders.yaml"
    ).exists()
