import copy

import pytest
import yaml

import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module
from dw_refactor_agent.assessment.llm.inspection_issues import (
    ParsedInspectionCandidate,
    issue_for_code,
)
from dw_refactor_agent.assessment.llm.inspection_recovery import (
    RecoveredInspectionCandidate,
)
from tests.assess.model_metadata_writer_test_support import (
    _catalog_payload,
    _customer_subject,
    _order_detail_process,
    _write_catalog_project,
)

_EMPTY_COLUMNS = {
    "atomic_metrics": [],
    "derived_metrics": [],
    "calculated_metrics": [],
    "dimensions": [],
    "others": [],
}
_FULL_EXECUTION = {
    "materialized": "full",
    "full_refresh_strategy": "replace_all",
}


def _formal_file_snapshot(project_dir):
    paths = [
        project_dir / "business_taxonomy.yaml",
        project_dir / "business_processes.yaml",
        project_dir / "semantic_subjects.yaml",
    ]
    paths.extend(sorted((project_dir / "mid" / "models").glob("*.yaml")))
    return {path: path.read_bytes() for path in paths if path.exists()}


def _report(table_name, payload, *, issue=None, issues=()):
    issue_items = list(issues)
    if issue is not None:
        issue_items.append(issue)
    return {
        "table_name": table_name,
        "declared_layer": payload["inferred_layer"],
        "status": "passed" if not issue_items else "blocked",
        "issues": [item.to_dict() for item in issue_items],
        "parsed_candidate": ParsedInspectionCandidate.create(
            table_name=table_name,
            raw_response_hash=f"raw-{table_name}",
            payload=payload,
        ).to_dict(),
        "recovered_candidate": RecoveredInspectionCandidate.create(
            table_name=table_name,
            payload=payload,
            repair_audit=(),
        ).to_dict(),
        **copy.deepcopy(payload),
    }


def _update(table_name, metadata):
    return {
        "table": table_name,
        "status": "passed",
        "changed": True,
        "updated": False,
        "model_metadata": metadata,
    }


def test_generate_publishes_complete_v3_set_with_isolated_quarantine(
    tmp_path, monkeypatch
):
    project = "governed_mixed_publication"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(
            processes=[_order_detail_process("SALE")],
            subjects=[_customer_subject()],
        ),
        ddl_tables=["dwd_source", "dim_customer"],
    )
    source_entities = [
        {"code": "ORDER", "type": "primary", "key_columns": ["id"]}
    ]
    source_grain = {"entities": ["ORDER"]}
    source_columns = {
        "atomic_metrics": [{"name": "subtotal", "business_process": "SALE"}],
        "derived_metrics": [],
        "calculated_metrics": [],
        "dimensions": [],
        "others": [],
    }
    source_model = {
        "version": 2,
        "name": "dwd_source",
        "layer": "DWD",
        "table_type": "fact",
        "business_process": "SALE",
        "entities": source_entities,
        "grain": source_grain,
        "atomic_metrics": source_columns["atomic_metrics"],
        "execution": _FULL_EXECUTION,
    }
    dimension_entities = [
        {
            "code": "CUSTOMER",
            "type": "primary",
            "key_columns": ["customer_id"],
        }
    ]
    dimension_grain = {"entities": ["CUSTOMER"]}
    dimension_model = {
        "version": 2,
        "name": "dim_customer",
        "layer": "DIM",
        "table_type": "dimension",
        "semantic_subject": "CUSTOMER",
        "entities": dimension_entities,
        "grain": dimension_grain,
        "execution": _FULL_EXECUTION,
    }
    reports = [
        _report(
            "dwd_source",
            {
                "inferred_layer": "DWD",
                "table_type": "fact",
                "business_process": "SALE",
                "columns": source_columns,
                "entities": source_entities,
                "grain": source_grain,
            },
            issue=issue_for_code(
                "invalid_base_metrics",
                table="dwd_source",
                path="columns.atomic_metrics.subtotal",
            ),
        ),
        _report(
            "dim_customer",
            {
                "inferred_layer": "DIM",
                "table_type": "dimension",
                "columns": _EMPTY_COLUMNS,
                "entities": dimension_entities,
                "grain": dimension_grain,
            },
        ),
    ]
    monkeypatch.setattr(
        writer_module,
        "run_metadata_write",
        lambda *args, **kwargs: {
            "tables": reports,
            "model_updates": [
                _update("dwd_source", source_model),
                _update("dim_customer", dimension_model),
            ],
            "local_section_decisions": [],
        },
    )

    result = writer_module.run_generate_model_metadata(
        project,
        api_key="test",
        dry_run=False,
    )

    model_paths = sorted((project_dir / "mid" / "models").glob("*.yaml"))
    models = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in model_paths
    }
    assert result["publication"]["status"] == "published_with_quarantine"
    assert set(models) == {"dwd_source", "dim_customer"}
    assert all(model["version"] == 3 for model in models.values())
    assert models["dwd_source"]["governance"]["withheld_sections"] == [
        "metrics"
    ]
    assert "atomic_metrics" not in models["dwd_source"]
    assert "derived_metrics" not in models["dwd_source"]
    assert "calculated_metrics" not in models["dwd_source"]
    assert "governance" not in models["dim_customer"]
    assert models["dim_customer"]["semantic_subject"] == "CUSTOMER"
    formal_catalog = "\n".join(
        (project_dir / name).read_text(encoding="utf-8")
        for name in (
            "business_taxonomy.yaml",
            "business_processes.yaml",
            "semantic_subjects.yaml",
        )
    ).casefold()
    assert "proposal" not in formal_catalog
    assert "quarantin" not in formal_catalog


def test_require_complete_preserves_all_formal_files_and_maps_exit_two(
    tmp_path, monkeypatch
):
    project = "governed_strict_publication"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
        models={
            "legacy": {
                "version": 2,
                "name": "legacy",
                "layer": "DWD",
            }
        },
    )
    before = _formal_file_snapshot(project_dir)

    result = writer_module.run_generate_model_metadata(
        project,
        dry_run=False,
        require_complete=True,
    )
    dry_run = writer_module.run_generate_model_metadata(
        project,
        dry_run=True,
        require_complete=True,
    )

    assert result["publication"]["status"] == "not_published_incomplete"
    assert result["publication"]["candidate_status"] == "quarantined"
    assert writer_module.publication_exit_code(result["publication"]) == 2
    assert dry_run["publication"]["status"] == "dry_run"
    assert (
        dry_run["publication"]["would_publish_status"]
        == "not_published_incomplete"
    )
    assert writer_module.publication_exit_code(dry_run["publication"]) == 2
    assert _formal_file_snapshot(project_dir) == before


@pytest.mark.parametrize(
    ("publication", "expected"),
    [
        ({"status": "published", "published": True}, 0),
        ({"status": "published_with_quarantine", "published": True}, 0),
        ({"status": "blocked", "published": False}, 1),
        ({"status": "not_published_inspection_failure"}, 2),
        (
            {
                "status": "published",
                "published": True,
                "finalization_status": "failed",
            },
            3,
        ),
    ],
)
def test_publication_exit_code_contract(publication, expected):
    assert writer_module.publication_exit_code(publication) == expected


def test_result_report_failure_after_publication_exits_three(
    tmp_path, monkeypatch, capsys
):
    publication = {
        "status": "published_with_quarantine",
        "candidate_status": "quarantined",
        "published": True,
        "formal_files_state": "published",
        "finalization_status": "completed",
    }

    def fail_write(self, *args, **kwargs):
        raise OSError("report filesystem is read-only")

    monkeypatch.setattr(type(tmp_path), "write_text", fail_write)
    with pytest.raises(SystemExit) as exc_info:
        writer_module._write_result_report(
            tmp_path / "result.json", {"publication": publication}
        )

    assert exc_info.value.code == 3
    assert publication["finalization_status"] == "failed"
    assert publication["recovery_required"] is True
    assert "正式文件已经发布" in capsys.readouterr().err


def test_generate_hard_block_count_matches_final_validation_errors(
    tmp_path, monkeypatch
):
    project = "governed_hard_block_count"
    project_dir = _write_catalog_project(
        tmp_path,
        monkeypatch,
        project,
        catalog=_catalog_payload(),
        ddl_tables=["dwd_order_detail"],
    )
    report = _report(
        "dwd_order_detail",
        {
            "inferred_layer": "DWD",
            "table_type": "fact",
            "columns": {},
            "entities": [],
            "grain": {},
        },
        issues=(
            issue_for_code(
                "internal_inspection_error", table="dwd_order_detail"
            ),
            issue_for_code(
                "metric_propagation_not_converged",
                table="dwd_order_detail",
            ),
        ),
    )
    monkeypatch.setattr(
        writer_module,
        "run_metadata_write",
        lambda *args, **kwargs: {
            "tables": [report],
            "model_updates": [],
            "local_section_decisions": [],
        },
    )

    result = writer_module.run_generate_model_metadata(project, api_key="test")

    publication = result["publication"]
    assert publication["status"] == "blocked"
    assert (
        publication["hard_block_count"]
        == (publication["validation"]["error_count"])
    )
    assert publication["hard_block_count"] >= 2
    assert not (project_dir / "mid/models/dwd_order_detail.yaml").exists()
