from __future__ import annotations

import pytest

import dw_refactor_agent.execution.schedule_cli as schedule_cli
from dw_refactor_agent.execution.dag_executor import execute_dag
from dw_refactor_agent.execution.schedule_graph import (
    ScheduleContractError,
    ScheduleGraph,
)
from dw_refactor_agent.lineage.schedule_inference import (
    infer_schedule_candidate,
    validate_schedule_against_lineage,
)


def _multiwriter_lineage():
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "final_report",
                "full_name": "internal.demo.final_report",
                "dataset_type": "managed",
                "columns": [],
            },
            {
                "name": "shared_daily",
                "full_name": "internal.demo.shared_daily",
                "dataset_type": "managed",
                "columns": [],
            },
        ],
        "jobs": [
            {
                "name": "consume_shared",
                "source_file": "mid/tasks/consume_shared.sql",
                "inputs": ["internal.demo.shared_daily"],
                "outputs": ["internal.demo.final_report"],
            },
            {
                "name": "write_even",
                "source_file": "mid/tasks/write_even.sql",
                "inputs": [],
                "outputs": ["internal.demo.shared_daily"],
            },
            {
                "name": "write_odd",
                "source_file": "mid/tasks/write_odd.sql",
                "inputs": [],
                "outputs": ["internal.demo.shared_daily"],
            },
        ],
        "edges": [],
        "diagnostics": [],
    }


def _transitive_lineage():
    return {
        "format_version": 2,
        "tables": [
            {
                "name": "bridge_output",
                "full_name": "internal.demo.bridge_output",
                "dataset_type": "managed",
                "columns": [],
            },
            {
                "name": "final_output",
                "full_name": "internal.demo.final_output",
                "dataset_type": "managed",
                "columns": [],
            },
            {
                "name": "source_output",
                "full_name": "internal.demo.source_output",
                "dataset_type": "managed",
                "columns": [],
            },
        ],
        "jobs": [
            {
                "name": "bridge",
                "source_file": "mid/tasks/bridge.sql",
                "inputs": [],
                "outputs": ["internal.demo.bridge_output"],
            },
            {
                "name": "consumer",
                "source_file": "mid/tasks/consumer.sql",
                "inputs": ["internal.demo.source_output"],
                "outputs": ["internal.demo.final_output"],
            },
            {
                "name": "source",
                "source_file": "mid/tasks/source.sql",
                "inputs": [],
                "outputs": ["internal.demo.source_output"],
            },
        ],
        "edges": [],
        "diagnostics": [],
    }


def test_schedule_graph_contract_and_selected_subgraph():
    graph = ScheduleGraph(
        "demo",
        ["load", "transform", "report"],
        {"transform": ["load"], "report": ["transform"]},
    )

    assert graph.to_dict() == {
        "format_version": 1,
        "project": "demo",
        "jobs": ["load", "report", "transform"],
        "dependencies": {
            "report": ["transform"],
            "transform": ["load"],
        },
    }
    assert graph.topological_sort(graph.jobs) == [
        "load",
        "transform",
        "report",
    ]
    assert graph.selected_dependencies({"transform", "report"}) == {
        "report": ["transform"],
        "transform": [],
    }
    assert graph.omitted_upstreams({"transform", "report"}) == {
        "transform": ["load"]
    }


def test_schedule_graph_rejects_cycles_and_unknown_fields():
    with pytest.raises(ScheduleContractError, match="contains a cycle"):
        ScheduleGraph("demo", ["a", "b"], {"a": ["b"], "b": ["a"]})

    with pytest.raises(ScheduleContractError, match="unsupported fields"):
        ScheduleGraph.from_dict(
            {
                "format_version": 1,
                "project": "demo",
                "jobs": [],
                "dependencies": {},
                "source": "scheduler",
            }
        )


def test_lineage_inference_keeps_multiwriters_unordered_but_orders_consumer():
    candidate, diagnostics, evidence = infer_schedule_candidate(
        _multiwriter_lineage(), "demo"
    )

    assert candidate.edges == {
        ("write_even", "consume_shared"),
        ("write_odd", "consume_shared"),
    }
    assert not candidate.has_path("write_even", "write_odd")
    assert not candidate.has_path("write_odd", "write_even")
    assert [item["code"] for item in diagnostics] == ["MULTIPLE_WRITERS"]
    assert all(item["multiple_writer_input"] for item in evidence)


def test_lineage_validation_warns_when_one_writer_is_not_ordered():
    trusted = ScheduleGraph(
        "demo",
        ["write_even", "write_odd", "consume_shared"],
        {"consume_shared": ["write_even"]},
    )

    diagnostics = validate_schedule_against_lineage(
        trusted, _multiwriter_lineage()
    )
    codes = [item["code"] for item in diagnostics]

    assert "LINEAGE_DEPENDENCY_NOT_ORDERED" in codes
    assert "UNORDERED_MULTIPLE_WRITERS" in codes


def test_dag_executor_blocks_only_failed_job_descendants():
    executed = []

    def run_job(job):
        executed.append(job)
        if job == "failed_writer":
            raise RuntimeError("writer failed")
        return job.upper()

    results = execute_dag(
        ["failed_writer", "dependent", "independent"],
        {"dependent": ["failed_writer"]},
        run_job,
        parallel=2,
        order=["failed_writer", "independent", "dependent"],
    )

    assert set(executed) == {"failed_writer", "independent"}
    assert results["failed_writer"].status == "failed"
    assert results["dependent"].status == "blocked"
    assert results["dependent"].blocked_by == ("failed_writer",)
    assert results["independent"].status == "success"
    assert results["independent"].value == "INDEPENDENT"


def test_reconcile_does_not_add_redundant_direct_edge(
    tmp_path, monkeypatch, capsys
):
    schedule_path = tmp_path / "job_dag.json"
    ScheduleGraph(
        "demo",
        ["source", "bridge", "consumer"],
        {"bridge": ["source"], "consumer": ["bridge"]},
    ).save(schedule_path)
    monkeypatch.setattr(
        schedule_cli,
        "configured_schedule_path",
        lambda _project: schedule_path,
    )
    monkeypatch.setattr(
        schedule_cli,
        "_read_lineage",
        lambda _project, _path: _transitive_lineage(),
    )
    monkeypatch.setattr(
        schedule_cli,
        "_task_names",
        lambda _project: {"source", "bridge", "consumer"},
    )
    args = type(
        "Args",
        (),
        {
            "project": "demo",
            "lineage": None,
            "apply_safe": True,
        },
    )()

    assert schedule_cli._reconcile(args) == 0
    persisted = ScheduleGraph.load(schedule_path, expected_project="demo")
    assert persisted.direct_upstreams("consumer") == {"bridge"}
    assert '"safe_edges": []' in capsys.readouterr().out


def test_reconcile_reports_removed_jobs_without_deleting_them(
    tmp_path, monkeypatch, capsys
):
    schedule_path = tmp_path / "job_dag.json"
    ScheduleGraph(
        "demo",
        ["source", "bridge", "consumer", "obsolete"],
        {"bridge": ["source"], "consumer": ["bridge"]},
    ).save(schedule_path)
    monkeypatch.setattr(
        schedule_cli,
        "configured_schedule_path",
        lambda _project: schedule_path,
    )
    monkeypatch.setattr(
        schedule_cli,
        "_read_lineage",
        lambda _project, _path: _transitive_lineage(),
    )
    monkeypatch.setattr(
        schedule_cli,
        "_task_names",
        lambda _project: {"source", "bridge", "consumer"},
    )
    args = type(
        "Args",
        (),
        {
            "project": "demo",
            "lineage": None,
            "apply_safe": False,
        },
    )()

    assert schedule_cli._reconcile(args) == 0
    output = capsys.readouterr().out
    assert '"removed_jobs_manual_review": [' in output
    assert '"obsolete"' in output
    assert (
        ScheduleGraph.load(schedule_path, expected_project="demo").resolve_job(
            "obsolete"
        )
        == "obsolete"
    )
