"""Asset completeness scoring dimension."""
from __future__ import annotations

from assess.result_model import finalize_dimension, make_check
from assess.scoring.config import (
    ASSET_COMPLETENESS_RULES,
    ASSET_RULE_DDL_MODEL,
    ASSET_RULE_DDL_TASK,
    ASSET_RULE_IDS,
    ASSET_RULE_MODEL_DDL,
    ASSET_RULE_TABLE_SINGLE_WRITER,
    ASSET_RULE_TASK_DDL,
    ASSET_RULE_TASK_LINEAGE,
    ASSET_RULE_TASK_MODEL,
    ASSET_RULE_TASK_SINGLE_OUTPUT,
)


def _asset_requires_task(asset: dict) -> bool:
    model = asset.get("model") or {}
    metadata = model.get("metadata") or {}
    layer = str(asset.get("layer") or "OTHER").upper()
    materialized = str(
        (metadata.get("config") or {}).get("materialized") or ""
    ).lower()
    return layer != "ODS" and materialized != "source"


def _logical_task_key(task: dict) -> str:
    return str(task.get("expected_table") or task.get("file") or "")


def score_asset_completeness(asset_catalog: dict) -> dict:
    """Score DDL/model/task closure and task-lineage consistency."""
    checks = []

    def record(
        asset_name: str,
        rule: str,
        ok: bool,
        message: str,
        *,
        target_type: str = "table",
        expected: str | None = None,
        actual: str | None = None,
        evidence: dict | None = None,
    ) -> None:
        checks.append(
            make_check(
                rule_id=ASSET_RULE_IDS[rule],
                target_type=target_type,
                target=asset_name,
                passed=ok,
                expected=expected or rule,
                actual=actual or ("满足" if ok else message),
                evidence=evidence,
                message="" if ok else message,
            )
        )

    assets = asset_catalog.get("tables") or {}
    for name, asset in sorted(assets.items()):
        has_ddl = bool(asset.get("ddl"))
        has_model = bool(asset.get("model"))
        tasks = asset.get("tasks") or []
        has_output_task = any(
            name in task.get("output_tables", set())
            for task in tasks
        )

        if has_ddl:
            record(
                name,
                ASSET_RULE_DDL_MODEL,
                has_model,
                "缺少Model",
                expected="DDL表存在Model",
                actual="已存在Model" if has_model else "未找到Model",
            )
            if _asset_requires_task(asset):
                record(
                    name,
                    ASSET_RULE_DDL_TASK,
                    has_output_task,
                    "缺少产出该表的Task",
                    expected="非ODS且非source物化表存在产出Task",
                    actual=(
                        "已存在产出Task"
                        if has_output_task
                        else "未找到产出Task"
                    ),
                )

        if has_model:
            record(
                name,
                ASSET_RULE_MODEL_DDL,
                has_ddl,
                "缺少DDL",
                expected="Model存在对应DDL表",
                actual="已存在DDL" if has_ddl else "未找到DDL",
            )

    task_outputs = sorted({
        output
        for task in asset_catalog.get("tasks") or []
        for output in task.get("output_tables", set())
    })
    for task in asset_catalog.get("tasks") or []:
        outputs = sorted(set(task.get("output_tables") or set()))
        actual = f"实际产出={outputs}"
        record(
            task["file"],
            ASSET_RULE_TASK_SINGLE_OUTPUT,
            len(outputs) == 1,
            "Task必须有且只有一个持久产出表",
            target_type="task",
            expected="Task有且只有一个持久产出表",
            actual=actual,
            evidence={"outputs": outputs},
        )

    for output in task_outputs:
        asset = assets.get(output, {})
        record(
            output,
            ASSET_RULE_TASK_DDL,
            bool(asset.get("ddl")),
            "Task产出表缺少DDL",
            expected="Task产出表存在DDL",
            actual="已存在DDL" if asset.get("ddl") else "未找到DDL",
        )
        record(
            output,
            ASSET_RULE_TASK_MODEL,
            bool(asset.get("model")),
            "Task产出表缺少Model",
            expected="Task产出表存在Model",
            actual="已存在Model" if asset.get("model") else "未找到Model",
        )

    writers_by_output = {}
    for task in asset_catalog.get("tasks") or []:
        for output in task.get("output_tables") or set():
            writers_by_output.setdefault(output, {}).setdefault(
                _logical_task_key(task),
                set(),
            ).add(task["file"])

    for output, writers_by_key in sorted(writers_by_output.items()):
        writer_files = sorted({
            file_name
            for files in writers_by_key.values()
            for file_name in files
        })
        actual = f"产出Task={writer_files}"
        record(
            output,
            ASSET_RULE_TABLE_SINGLE_WRITER,
            len(writers_by_key) == 1,
            "目标表必须有且只有一个逻辑产出Task",
            expected="目标表有且只有一个逻辑产出Task",
            actual=actual,
            evidence={
                "writers": writer_files,
                "logical_writers": sorted(writers_by_key),
            },
        )

    for task in asset_catalog.get("tasks") or []:
        outputs = set(task.get("output_tables") or set())
        lineage_targets = set(task.get("lineage_targets") or set())
        actual = (
            f"实际产出={sorted(outputs)}，"
            f"血缘目标={sorted(lineage_targets)}"
        )
        record(
            task["file"],
            ASSET_RULE_TASK_LINEAGE,
            bool(outputs) and lineage_targets == outputs,
            actual,
            target_type="task",
            expected="Task血缘目标与实际产出一致",
            actual=actual,
            evidence={
                "outputs": sorted(outputs),
                "lineage_targets": sorted(lineage_targets),
            },
        )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="asset_completeness",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=ASSET_COMPLETENESS_RULES,
    )
