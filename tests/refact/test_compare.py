import json
from copy import deepcopy

import pytest

import dw_refactor_agent.refactor.compare as compare_module
from dw_refactor_agent.refactor.artifact_contract import ArtifactFormatError
from dw_refactor_agent.refactor.compare import (
    check_row_compare,
    compare_shadow_results,
    fmt_val,
    run_checks,
)
from dw_refactor_agent.refactor.compare import (
    main as compare_main,
)
from dw_refactor_agent.refactor.plan_artifact import (
    analysis_input_fingerprints,
    write_verification_plan,
)
from dw_refactor_agent.refactor.session import write_manifest
from dw_refactor_agent.refactor.workspace_snapshot import workspace_fingerprint


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.executed = []

    def execute(self, sql):
        self.executed.append(sql)

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)

    def close(self):
        pass


class FakeConn:
    def __init__(self, cursors):
        self.cursors = list(cursors)
        self.closed = False

    def cursor(self):
        return self.cursors.pop(0)

    def close(self):
        self.closed = True


def _semantic_verification(
    checks, modes=None, warnings=None, scopes=None, **values
):
    modes = modes or {}
    scopes = scopes or {}
    grouped = {}
    for check in checks:
        table = check["table"]
        group = grouped.setdefault(
            table,
            {
                "table": table,
                "scope": deepcopy(scopes.get(table) or {"mode": "full_table"}),
                "methods": [],
            },
        )
        for field in ("prod_table", "qa_table", "column_mapping"):
            if field in check:
                group[field] = deepcopy(check[field])
        method = {"method": check["method"]}
        if "exclude_columns" in check:
            method["exclude_columns"] = list(check["exclude_columns"])
        group["methods"].append(method)
    verification = {
        "checks": list(grouped.values()),
        "target_semantics": {
            check["table"]: {
                "resolved_mode": modes.get(check["table"], "equivalent")
            }
            for check in checks
        },
    }
    if warnings is not None:
        verification["warnings"] = warnings
    verification.update(values)
    return verification


def _write_compare_plan(plan_path, verification):
    root = plan_path.parent.parent
    warehouse_path = root / "warehouses" / "shop" / "warehouse.yaml"
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    warehouse_path.write_text(
        "name: shop\ndatabase: shop_dm\nqa_database: shop_dm_qa\n",
        encoding="utf-8",
    )
    manifest = {
        "format_version": 1,
        "run_id": "test-run",
        "project": "shop",
        "root": str(root),
        "artifacts": {
            "baseline_lineage": "baseline/lineage.json",
            "current_lineage": "current/lineage.json",
            "change_analysis": "analysis/change.json",
            "verification_plan": "verification/plan.json",
        },
        "verification_intent": {"semantic_modes": {}},
    }
    write_manifest(root / "manifest.json", manifest)
    inputs = {
        "baseline_lineage": {"tables": [], "edges": []},
        "current_lineage": {"tables": [], "edges": []},
        "change_analysis": {"changed_files": []},
    }
    for artifact_name, value in inputs.items():
        artifact_path = root / manifest["artifacts"][artifact_name]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(value), encoding="utf-8")

    plan = {
        "run_id": "test-run",
        "project": "shop",
        "project_db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "qa_database_pool": ["shop_dm_qa", "shop_dm_qa_02"],
        "baseline_ddl": {},
        "ddl_changes": [],
        "jobs_to_run": [],
        "execution_graph": {
            "format_version": 1,
            "project": "shop",
            "jobs": [],
            "dependencies": {},
        },
        "verification": deepcopy(verification),
        "analysis_snapshot": {
            "partition": "2024-12-31",
            "workspace_fingerprint": workspace_fingerprint(root, "shop"),
            "analysis_inputs": analysis_input_fingerprints(
                manifest=manifest,
                baseline_lineage=inputs["baseline_lineage"],
                current_lineage=inputs["current_lineage"],
                change_analysis=inputs["change_analysis"],
            ),
        },
    }
    return write_verification_plan(plan_path, plan)


def _write_shadow_result(shadow_path, persisted_plan, **overrides):
    result = {
        "format_version": 1,
        "mode": "execute",
        "status": "completed",
        "run_id": "test-run",
        "execution_id": "execution-123",
        "qa_db": "shop_dm_qa",
        "workspace_fingerprint": persisted_plan["analysis_snapshot"][
            "workspace_fingerprint"
        ],
        "plan_fingerprint": persisted_plan["plan_fingerprint"],
    }
    result.update(overrides)
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text(json.dumps(result), encoding="utf-8")


def test_fmt_val_formats_supported_scalar_values():
    scenarios = [
        (None, "NULL"),
        (123, "123"),
        (3.14159, "3.141590"),
        ("hello", "hello"),
    ]

    for value, expected in scenarios:
        assert fmt_val(value) == expected


def test_run_checks_uses_compare_anchor_for_partition_filter(monkeypatch):
    prod_cursor = FakeCursor([(3,)])
    qa_cursor = FakeCursor([(3,)])
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    def fake_conn(db_name, qa=False):
        return qa_conn if qa else prod_conn

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn", fake_conn
    )

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": _semantic_verification(
                [{"table": "ads_store_performance", "method": "count"}],
                scopes={
                    "ads_store_performance": {
                        "mode": "time_slice",
                        "column": "stat_month_date",
                        "period": "M",
                        "value": "2024-06-01",
                    }
                },
            ),
        },
        method="count",
    )

    assert result["verification_status"] == "passed"
    assert prod_cursor.executed == [
        "SELECT COUNT(*) FROM ads_store_performance "
        "WHERE stat_month_date = '2024-06-01'"
    ]
    assert qa_cursor.executed == prod_cursor.executed


def test_row_compare_excludes_configured_columns_case_insensitively():
    prod_cursor = FakeCursor(
        [
            [("order_id",), ("amount",), ("etl_time",)],
            [(1, 10, "2026-07-04 10:00:00")],
        ]
    )
    qa_cursor = FakeCursor(
        [
            [(1, 10, "2026-07-04 10:05:00")],
        ]
    )
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {
            "table": "dws_order",
            "method": "row_compare",
            "exclude_columns": ["ETL_TIME"],
        },
        sample=0,
        precision=0.01,
    )

    assert result["match"] is True
    assert result["compared_columns"] == ["order_id", "amount"]
    assert result["ignored_columns"] == ["etl_time"]
    assert prod_cursor.executed == [
        "DESC dws_order",
        "SELECT order_id, amount FROM dws_order ORDER BY order_id, amount ",
    ]
    assert qa_cursor.executed == [
        "SELECT order_id, amount FROM dws_order ORDER BY order_id, amount ",
    ]


def test_row_compare_empty_exclude_columns_compares_all_columns():
    prod_cursor = FakeCursor(
        [
            [("order_id",), ("amount",), ("etl_time",)],
            [(1, 10, "2026-07-04 10:00:00")],
        ]
    )
    qa_cursor = FakeCursor(
        [
            [(1, 10, "2026-07-04 10:05:00")],
        ]
    )
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {
            "table": "dws_order",
            "method": "row_compare",
            "exclude_columns": [],
        },
        sample=0,
        precision=0.01,
    )

    assert result["match"] is False
    assert result["compared_columns"] == ["order_id", "amount", "etl_time"]
    assert result["ignored_columns"] == []
    assert result["detail"] == [
        {
            "row": 0,
            "diffs": [
                {
                    "col": "etl_time",
                    "prod": "2026-07-04 10:00:00",
                    "qa": "2026-07-04 10:05:00",
                }
            ],
        }
    ]


def test_row_compare_missing_columns_returns_failed_result():
    result = check_row_compare(
        FakeConn([FakeCursor([[]])]),
        FakeConn([FakeCursor([])]),
        {"table": "empty_table", "method": "row_compare"},
        sample=0,
        precision=0.01,
    )

    assert result["match"] is False
    assert result["error"] == "无列信息"


def test_renamed_count_uses_distinct_prod_and_qa_tables(monkeypatch):
    prod_cursor = FakeCursor([(4,)])
    qa_cursor = FakeCursor([(4,)])
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn",
        lambda db_name, qa=False: qa_conn if qa else prod_conn,
    )

    verification = _semantic_verification(
        [
            {
                "table": "dim_store",
                "prod_table": "dwd_store",
                "qa_table": "dim_store",
                "method": "count",
            }
        ],
        scopes={
            "dim_store": {
                "mode": "time_slice",
                "column": "STAT_DATE",
                "period": "D",
                "value": "2024-12-31",
            }
        },
    )
    verification["target_semantics"]["dim_store"]["column_mapping"] = [
        {"column_id": "date", "prod": "stat_date", "qa": "STAT_DATE"}
    ]

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": verification,
        },
        method="count",
    )

    assert result["verification_status"] == "passed"
    assert prod_cursor.executed == [
        "SELECT COUNT(*) FROM dwd_store WHERE stat_date = '2024-12-31'"
    ]
    assert qa_cursor.executed == [
        "SELECT COUNT(*) FROM dim_store WHERE STAT_DATE = '2024-12-31'"
    ]


def test_renamed_row_compare_maps_qa_exclusions_and_projections():
    prod_cursor = FakeCursor([[(1, "A")]])
    qa_cursor = FakeCursor([[(1, "A")]])
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])

    result = check_row_compare(
        prod_conn,
        qa_conn,
        {
            "table": "dim_store",
            "prod_table": "dwd_store",
            "qa_table": "dim_store",
            "method": "row_compare",
            "exclude_columns": ["LOAD_TIME"],
            "column_mapping": [
                {"column_id": "1", "prod": "store_id", "qa": "STORE_ID"},
                {"column_id": "2", "prod": "name", "qa": "STORE_NAME"},
                {
                    "column_id": "3",
                    "prod": "etl_time",
                    "qa": "LOAD_TIME",
                },
            ],
        },
        sample=0,
        precision=0.01,
    )

    assert result["match"] is True
    assert result["compared_columns"] == ["STORE_ID", "STORE_NAME"]
    assert result["ignored_columns"] == ["LOAD_TIME"]
    assert prod_cursor.executed == [
        "SELECT store_id, name FROM dwd_store ORDER BY store_id, name "
    ]
    assert qa_cursor.executed == [
        "SELECT STORE_ID, STORE_NAME FROM dim_store "
        "ORDER BY STORE_ID, STORE_NAME "
    ]


def test_run_checks_short_circuit_scenarios(monkeypatch):
    def fail_if_called(db_name, qa=False):
        raise AssertionError("short-circuit plans should not open connections")

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn", fail_if_called
    )

    scenarios = [
        (
            "no_data_anchor",
            {
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "affected_scope": {"direct_tables": ["dws_terminal"]},
                "jobs_to_run": [
                    {
                        "job": "dws_terminal",
                        "target": "dws_terminal",
                    }
                ],
                "verification": {
                    "checks": [],
                    "target_semantics": {},
                    "data_anchor_status": "none",
                    "data_anchor_reason": (
                        "no invariant downstream anchor tables"
                    ),
                },
            },
            {
                "verification_status": "inconclusive",
                "reason": "no invariant downstream anchor tables",
                "warnings": [],
                "comparison": {
                    "method": "count",
                    "sample": 0,
                    "precision": 0.01,
                    "required_checks": [],
                    "executed_checks": [],
                    "complete": True,
                },
                "results": [],
            },
        ),
        (
            "schema_anchor_blocked",
            {
                "project_db": "shop_dm",
                "qa_db": "shop_dm_qa",
                "verification": {
                    "schema_anchor_status": "blocked",
                    "schema_anchor_reason": (
                        "ADS table definitions must remain unchanged"
                    ),
                    "checks": [
                        {
                            "table": "ads_final",
                            "scope": {"mode": "full_table"},
                            "methods": [{"method": "count"}],
                        }
                    ],
                },
            },
            {
                "verification_status": "blocked",
                "reason": "ADS table definitions must remain unchanged",
                "warnings": [],
                "comparison": {
                    "method": "count",
                    "sample": 0,
                    "precision": 0.01,
                    "required_checks": ["ads_final:count"],
                    "executed_checks": [],
                    "complete": False,
                },
                "results": [],
            },
        ),
    ]

    for scenario_name, plan, expected in scenarios:
        assert run_checks(plan, method="count") == expected, scenario_name


@pytest.mark.parametrize(
    ("mode", "counts", "warnings", "expected"),
    [
        ("equivalent", [(5,), (5,)], [], "passed"),
        ("equivalent", [(5,), (4,)], [], "failed"),
        (
            "unknown",
            [(5,), (5,)],
            [{"type": "unknown_table_semantics", "table": "dws_order"}],
            "passed_with_warnings",
        ),
        (
            "unknown",
            [(5,), (4,)],
            [{"type": "unknown_table_semantics", "table": "dws_order"}],
            "inconclusive",
        ),
    ],
)
def test_run_checks_derives_five_state_semantic_result(
    mode, counts, warnings, expected, monkeypatch
):
    prod_conn = FakeConn([FakeCursor([counts[0]])])
    qa_conn = FakeConn([FakeCursor([counts[1]])])
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn",
        lambda db_name, qa=False: qa_conn if qa else prod_conn,
    )

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": _semantic_verification(
                [{"table": "dws_order", "method": "count"}],
                modes={"dws_order": mode},
                warnings=warnings,
            ),
        },
        method="count",
    )

    assert result["verification_status"] == expected
    assert result["warnings"] == warnings
    assert "all_pass" not in result


def test_sampled_row_compare_cannot_authoritatively_pass(monkeypatch):
    prod_cursor = FakeCursor([[("order_id",), ("amount",)], [(1, 10)]])
    qa_cursor = FakeCursor([[(1, 10)]])
    prod_conn = FakeConn([prod_cursor])
    qa_conn = FakeConn([qa_cursor])
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.get_pymysql_conn",
        lambda db_name, qa=False: qa_conn if qa else prod_conn,
    )

    result = run_checks(
        {
            "project_db": "shop_dm",
            "qa_db": "shop_dm_qa",
            "verification": _semantic_verification(
                [{"table": "dws_order", "method": "row_compare"}]
            ),
        },
        method="all",
        sample=1,
    )

    assert result["verification_status"] == "inconclusive"
    assert result["comparison"]["complete"] is False
    assert result["comparison"]["sample"] == 1


def test_compare_shadow_results_writes_compare_output(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = tmp_path / "verification" / "shadow_run_result.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    persisted_plan = _write_compare_plan(
        plan_path,
        _semantic_verification([]),
    )
    _write_shadow_result(shadow_path, persisted_plan)

    def fake_run_checks(meta, method="all", sample=0, precision=0.01):
        assert meta["baseline_ddl"] == {}
        return {
            "verification_status": "passed",
            "warnings": [],
            "results": [],
            "method": method,
            "sample": sample,
            "precision": precision,
        }

    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.run_checks", fake_run_checks
    )
    monkeypatch.setattr(
        compare_module,
        "load_verification_plan",
        lambda plan_path: (_ for _ in ()).throw(
            AssertionError("core must compare the validated bundle snapshot")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        compare_module,
        "require_slot_ownership",
        lambda **kwargs: None,
        raising=False,
    )

    result = compare_shadow_results(
        plan_path,
        shadow_path,
        output_path,
        method="count",
        sample=10,
        precision=0.1,
    )

    assert result["method"] == "count"
    assert result["sample"] == 10
    assert result["precision"] == 0.1
    assert result["format_version"] == 1
    assert result["shadow_execution_id"] == "execution-123"
    assert (
        result["workspace_fingerprint"]
        == persisted_plan["analysis_snapshot"]["workspace_fingerprint"]
    )
    assert result["plan_fingerprint"] == persisted_plan["plan_fingerprint"]
    assert result["shadow_result_fingerprint"].startswith("sha256:")
    assert "all_pass" not in result
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_compare_rejects_shadow_database_outside_pool_before_connections(
    tmp_path, monkeypatch
):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = tmp_path / "verification" / "shadow_run_result.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    persisted = _write_compare_plan(plan_path, _semantic_verification([]))
    _write_shadow_result(shadow_path, persisted, qa_db="shop_dm")
    database_connections = []
    monkeypatch.setattr(
        compare_module,
        "get_pymysql_conn",
        lambda *args, **kwargs: database_connections.append(args) or None,
    )
    monkeypatch.setattr(
        compare_module,
        "require_slot_ownership",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("pool validation must precede marker connection")
        ),
        raising=False,
    )

    with pytest.raises(ArtifactFormatError, match="not in.*pool"):
        compare_shadow_results(plan_path, shadow_path, output_path)

    assert database_connections == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "dry_run"},
        {"status": "failed"},
        {"workspace_fingerprint": "sha256:stale"},
        {"plan_fingerprint": "sha256:stale"},
        {"workspace_fingerprint": None},
        {"plan_fingerprint": None},
        {"execution_id": None},
        {"run_id": "other-run"},
        {"qa_db": None},
    ],
)
def test_compare_rejects_nonmatching_shadow_before_database(
    tmp_path, monkeypatch, overrides
):
    plan_path = tmp_path / "verification" / "plan.json"
    shadow_path = tmp_path / "verification" / "shadow_run_result.json"
    output_path = tmp_path / "verification" / "compare_result.json"
    persisted_plan = _write_compare_plan(
        plan_path,
        _semantic_verification([]),
    )
    _write_shadow_result(shadow_path, persisted_plan, **overrides)
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.run_checks",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("must reject provenance before comparison")
        ),
    )

    with pytest.raises(ArtifactFormatError):
        compare_shadow_results(plan_path, shadow_path, output_path)


def test_compare_standalone_cli_rejects_stale_plan(tmp_path, monkeypatch):
    plan_path = tmp_path / "verification" / "plan.json"
    _write_compare_plan(plan_path, _semantic_verification([]))
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.require_fresh_plan",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ArtifactFormatError(
                "stale_plan: workspace changed after analyze; run analyze again"
            )
        ),
    )
    monkeypatch.setattr(
        "dw_refactor_agent.refactor.compare.compare_shadow_results",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("stale plan must block compare")
        ),
    )

    with pytest.raises(SystemExit, match="stale_plan.*analyze"):
        compare_main(["--plan", str(plan_path)])
