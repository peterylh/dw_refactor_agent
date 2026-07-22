import json
import pickle

import pytest
import sqlglot
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.lineage import (
    import_lineage,
    lineage_extractor,
    refresh_lineage_html,
)
from dw_refactor_agent.lineage.task_cache import (
    TaskCacheMetadata,
    task_cache_key,
)
from dw_refactor_agent.refactor.incremental_lineage import (
    build_lineage_artifacts,
)
from dw_refactor_agent.sql.task_analysis import (
    resolve_project_tasks_analysis,
)
from dw_refactor_agent.sql.task_template import TemplateRenderError


def _contract():
    return {
        "version": 1,
        "strict": True,
        "startup_params": [
            {
                "prop": "etl_date",
                "type": "DATE",
                "source": "invocation.etl_date",
                "required": True,
            }
        ],
        "project_params": [
            {
                "prop": "cdm_schema",
                "type": "IDENTIFIER",
                "source": "project.cdm_schema",
                "required": True,
            }
        ],
        "local_params": [
            {
                "prop": "biz_date",
                "direct": "IN",
                "type": "DATE",
                "value": "${etl_date}",
                "render": {"format": "yyyyMMdd"},
            },
            {
                "prop": "run_table",
                "direct": "IN",
                "type": "IDENTIFIER",
                "value": {
                    "derive": {
                        "from": "biz_date",
                        "operation": "format_date",
                        "format": "yyyyMMdd",
                        "prefix": "tmp_run_",
                    }
                },
            },
        ],
        "usage": {
            "dynamic_relations": [
                {"prop": "run_table", "lifecycle": "invocation"}
            ]
        },
    }


def _configure_project(monkeypatch, tmp_path, *, include_template=True):
    project_dir = tmp_path / "warehouses" / "demo"
    tasks_dir = project_dir / "mid" / "tasks"
    tasks_dir.mkdir(parents=True)
    template_sql = (
        "INSERT INTO ${cdm_schema}.target_table\n"
        "SELECT 1 AS id, ${biz_date} AS data_dt\n"
        "FROM ${cdm_schema}.source_table;\n"
        "DROP TABLE IF EXISTS ${run_table};\n"
    )
    sql_path = tasks_dir / "template_job.sql"
    sql_path.write_text(
        template_sql if include_template else "SELECT 1;\n",
        encoding="utf-8",
    )
    if include_template:
        (tasks_dir / "template_job.yaml").write_text(
            yaml.safe_dump(_contract(), sort_keys=False),
            encoding="utf-8",
        )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        "demo",
        {
            "dir": "warehouses/demo",
            "catalog": "internal",
            "db": "logical_cdm",
            "task_templates": {
                "version": 1,
                "analysis": {
                    "startup": {"etl_date": "2000-02-29"},
                    "project": {
                        "cdm_schema": "logical_cdm",
                        "binding_for_another_task": "ignored_here",
                    },
                },
            },
        },
    )
    return project_dir, sql_path


def test_analysis_render_is_stable_parser_ready_and_uses_logical_bindings(
    monkeypatch,
    tmp_path,
):
    _project_dir, sql_path = _configure_project(monkeypatch, tmp_path)

    first_asset, first = resolve_project_tasks_analysis("demo")[0]
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    monkeypatch.chdir(other_dir)
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    second_asset, second = resolve_project_tasks_analysis("demo")[0]

    assert first_asset.sql_path == second_asset.sql_path == sql_path
    assert first.sql == second.sql
    assert first.analysis_identity == second.analysis_identity
    assert "${" not in first.sql
    assert "`logical_cdm`.target_table" in first.sql
    assert "'20000229' AS data_dt" in first.sql
    assert "`tmp_run_20000229`" in first.sql
    assert sqlglot.parse(first.sql, dialect="doris")
    assert set(first.analysis_identity) >= {
        "template_digest",
        "config_digest",
        "binding_digest",
        "render_digest",
        "analysis_sql_digest",
        "analysis_profile_digest",
        "renderer_version",
        "renderer_semantics_digest",
    }


def test_legacy_analysis_sql_remains_byte_identical(monkeypatch, tmp_path):
    _project_dir, sql_path = _configure_project(
        monkeypatch,
        tmp_path,
        include_template=False,
    )

    asset, resolved = resolve_project_tasks_analysis("demo")[0]

    assert resolved.sql == sql_path.read_text(encoding="utf-8")
    assert resolved.is_template is False
    assert resolved.analysis_identity["kind"] == "legacy"
    assert asset.source_file == "template_job.sql"


def test_analysis_profile_is_explicit_and_missing_roots_fail_closed(
    monkeypatch,
    tmp_path,
):
    _configure_project(monkeypatch, tmp_path)
    config.PROJECT_CONFIG["demo"]["task_templates"]["analysis"]["startup"] = {}

    with pytest.raises(TemplateRenderError) as raised:
        resolve_project_tasks_analysis("demo")

    assert raised.value.code == "template.render.missing_binding"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("template_digest", "sha256:changed-template"),
        ("config_digest", "sha256:changed-config"),
        ("binding_digest", "sha256:changed-binding"),
        ("render_digest", "sha256:changed-render"),
        ("analysis_profile_digest", "sha256:changed-profile"),
        ("renderer_version", "changed-renderer"),
    ],
)
def test_each_template_analysis_identity_component_invalidates_cache_key(
    monkeypatch,
    tmp_path,
    field,
    replacement,
):
    _configure_project(monkeypatch, tmp_path)
    _asset, resolved = resolve_project_tasks_analysis("demo")[0]
    base_identity = dict(resolved.analysis_identity)
    metadata = TaskCacheMetadata(
        sql_hash="sql",
        referenced_tables=("logical_cdm.source_table",),
        schema_slice_hash="schema",
        extractor_hash="extractor",
        project_config={"catalog": "internal", "db": "logical_cdm"},
        analysis_identity=base_identity,
    )
    changed_identity = dict(base_identity)
    changed_identity[field] = replacement
    changed = TaskCacheMetadata(
        sql_hash=metadata.sql_hash,
        referenced_tables=metadata.referenced_tables,
        schema_slice_hash=metadata.schema_slice_hash,
        extractor_hash=metadata.extractor_hash,
        project_config=metadata.project_config,
        analysis_identity=changed_identity,
    )

    assert task_cache_key(
        project="demo",
        source_file="template_job.sql",
        metadata=metadata,
    ) != task_cache_key(
        project="demo",
        source_file="template_job.sql",
        metadata=changed,
    )


def test_analysis_identity_is_pickle_safe_for_parallel_workers(
    monkeypatch,
    tmp_path,
):
    _configure_project(monkeypatch, tmp_path)
    asset, resolved = resolve_project_tasks_analysis("demo")[0]
    work_item = lineage_extractor.TaskWorkItem(
        index=0,
        source_file=asset.source_file,
        sql_text=resolved.sql,
        analysis_identity=dict(resolved.analysis_identity),
    )

    restored = pickle.loads(pickle.dumps(work_item))

    assert restored.sql_text == work_item.sql_text
    assert restored.analysis_identity == work_item.analysis_identity


def test_lineage_parallel_cache_consumes_analysis_sql_and_profile_identity(
    monkeypatch,
    tmp_path,
):
    project_dir, _sql_path = _configure_project(monkeypatch, tmp_path)
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_PROJECT",
        lineage_extractor.CURRENT_PROJECT,
    )
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_CATALOG",
        lineage_extractor.CURRENT_CATALOG,
    )
    monkeypatch.setattr(
        lineage_extractor,
        "CURRENT_DB",
        lineage_extractor.CURRENT_DB,
    )
    lineage_extractor.configure_project("demo")
    schema = {
        "logical_cdm": {
            "source_table": {"id": "INT"},
            "target_table": {"id": "INT", "data_dt": "DATE"},
        }
    }
    cache_path = tmp_path / "task-cache.json"

    def extract(resolved_tasks, previous_cache):
        asset, resolved = resolved_tasks[0]
        return lineage_extractor.extract_lineage_from_task_files(
            [asset.sql_path],
            project_dir,
            schema,
            parallel=2,
            previous_cache_file=previous_cache,
            cache_project="demo",
            source_file_for_path=lambda path: asset.source_file,
            task_sql_resolver=lambda path: resolved,
        )

    cold = extract(resolve_project_tasks_analysis("demo"), cache_path)
    assert cold["task_results"][0].get("cache_hit") is not True
    assert cold["task_results"][0]["analysis_identity"]["kind"] == "template"
    cache_path.write_text(
        json.dumps(cold["task_cache"]),
        encoding="utf-8",
    )

    warm = extract(resolve_project_tasks_analysis("demo"), cache_path)
    assert warm["task_results"][0]["cache_hit"] is True

    config.PROJECT_CONFIG["demo"]["task_templates"]["analysis"]["startup"][
        "etl_date"
    ] = "2000-03-01"
    changed = extract(resolve_project_tasks_analysis("demo"), cache_path)
    assert changed["task_results"][0].get("cache_hit") is not True
    assert (
        changed["task_results"][0]["analysis_identity"]
        != warm["task_results"][0]["analysis_identity"]
    )


def test_assessment_asset_catalog_uses_rendered_sql_not_template_source(
    monkeypatch,
    tmp_path,
):
    project_dir, _sql_path = _configure_project(monkeypatch, tmp_path)

    catalog = build_asset_catalog([], {}, project_dir)

    assert len(catalog.tasks) == 1
    task = catalog.tasks[0]
    assert "${" not in task.sql
    assert "target_table" in task.output_tables


def test_assessment_resolves_project_when_config_key_differs_from_dir_name(
    monkeypatch,
    tmp_path,
):
    project_dir, _sql_path = _configure_project(monkeypatch, tmp_path)
    config.PROJECT_CONFIG["logical_demo"] = config.PROJECT_CONFIG.pop("demo")

    catalog = build_asset_catalog([], {}, project_dir)

    assert len(catalog.tasks) == 1
    assert "${" not in catalog.tasks[0].sql
    assert "target_table" in catalog.tasks[0].output_tables


def test_legacy_html_explicit_tasks_dir_uses_analysis_sql(
    monkeypatch,
    tmp_path,
):
    project_dir, _sql_path = _configure_project(monkeypatch, tmp_path)
    tasks_dir = project_dir / "mid" / "tasks"
    data = {
        "edges": [
            {
                "source": "source_table.id",
                "target": "target_table.id",
                "source_file": "template_job.sql",
            }
        ]
    }

    jobs = refresh_lineage_html.generate_jobs(
        data,
        tasks_dir=tasks_dir,
        current_db="logical_cdm",
        project="demo",
    )

    assert jobs[0]["target"].endswith("target_table")


def test_import_job_sql_uses_same_analysis_render(
    monkeypatch,
    tmp_path,
):
    project_dir, _sql_path = _configure_project(monkeypatch, tmp_path)
    data = {
        "edges": [
            {
                "source_file": "template_job.sql",
                "source": "source_table.id",
                "target": "target_table.id",
            }
        ]
    }

    rows = import_lineage.build_import_rows(
        data,
        tasks_dir=project_dir,
        context=import_lineage.ImportContext(
            project="demo",
            snapshot_id=42,
            datasource_id=1,
            datasource_name="logical_cdm",
            db_type="doris",
            host="127.0.0.1:9030",
        ),
    )

    job_sql = rows.job_rows[0][5]
    assert "${" not in job_sql
    assert "`logical_cdm`.target_table" in job_sql


def test_render_failure_preserves_existing_incremental_artifacts(
    monkeypatch,
    tmp_path,
):
    _configure_project(monkeypatch, tmp_path)
    config.PROJECT_CONFIG["demo"]["task_templates"]["analysis"]["startup"] = {}
    output_path = tmp_path / "lineage.json"
    cache_path = tmp_path / "cache.json"
    output_path.write_text("old-lineage", encoding="utf-8")
    cache_path.write_text("old-cache", encoding="utf-8")
    monkeypatch.setattr(
        lineage_extractor, "configure_project", lambda project: None
    )
    monkeypatch.setattr(
        lineage_extractor,
        "build_schema_from_project_ddl",
        lambda project: {},
    )

    with pytest.raises(TemplateRenderError):
        build_lineage_artifacts(
            "demo",
            output_path,
            cache_path,
        )

    assert output_path.read_text(encoding="utf-8") == "old-lineage"
    assert cache_path.read_text(encoding="utf-8") == "old-cache"
