"""Asset completeness rule definitions."""

from __future__ import annotations

from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    TableAsset,
    TaskAsset,
)
from dw_refactor_agent.assessment.result_model import make_check
from dw_refactor_agent.assessment.rules.engine.base import AssessRule
from dw_refactor_agent.lineage.identifiers import table_identity_match_key


class _AssetCompletenessRule(AssessRule):
    dimension = "asset_completeness"
    domain = "asset"

    def check(
        self,
        asset_name: str,
        ok: bool,
        message: str,
        *,
        target_type: str = "table",
        expected: str | None = None,
        actual: str | None = None,
        evidence: dict | None = None,
    ) -> dict:
        return make_check(
            rule_id=self.rule_id,
            target_type=target_type,
            target=asset_name,
            passed=ok,
            expected=expected or self.rule_id,
            actual=actual or ("满足" if ok else message),
            evidence=evidence,
            message="" if ok else message,
        )


class AssetDdlHasModelRule(_AssetCompletenessRule):
    rule_id = "ASSET_DDL_HAS_MODEL"
    target = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "table" or not target["has_ddl"]:
            return None
        return self.check(
            target["name"],
            target["has_model"],
            "缺少Model",
            expected="DDL表存在Model",
            actual="已存在Model" if target["has_model"] else "未找到Model",
        )


class AssetExecutableDdlHasTaskRule(_AssetCompletenessRule):
    rule_id = "ASSET_EXECUTABLE_DDL_HAS_TASK"
    target = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if (
            target["kind"] != "table"
            or not target["has_ddl"]
            or not _asset_requires_task(
                target["asset"],
                rule_context=rule_context,
            )
        ):
            return None
        return self.check(
            target["name"],
            target["has_output_task"],
            "缺少产出该表的Task",
            expected="非ODS且非source物化表存在产出Task",
            actual=(
                "已存在产出Task"
                if target["has_output_task"]
                else "未找到产出Task"
            ),
        )


class AssetModelHasDdlRule(_AssetCompletenessRule):
    rule_id = "ASSET_MODEL_HAS_DDL"
    target = "table"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "table" or not target["has_model"]:
            return None
        return self.check(
            target["name"],
            target["has_ddl"],
            "缺少DDL",
            expected="Model存在对应DDL表",
            actual="已存在DDL" if target["has_ddl"] else "未找到DDL",
        )


class AssetTaskOutputHasDdlRule(_AssetCompletenessRule):
    rule_id = "ASSET_TASK_OUTPUT_HAS_DDL"
    target = "task"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "output":
            return None
        asset = target["asset"]
        return self.check(
            target["output"],
            bool(asset.ddl),
            "Task产出表缺少DDL",
            expected="Task产出表存在DDL",
            actual="已存在DDL" if asset.ddl else "未找到DDL",
        )


class AssetTaskOutputHasModelRule(_AssetCompletenessRule):
    rule_id = "ASSET_TASK_OUTPUT_HAS_MODEL"
    target = "task"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "output":
            return None
        asset = target["asset"]
        return self.check(
            target["output"],
            bool(asset.model),
            "Task产出表缺少Model",
            expected="Task产出表存在Model",
            actual="已存在Model" if asset.model else "未找到Model",
        )


class AssetTaskSingleOutputRule(_AssetCompletenessRule):
    rule_id = "ASSET_TASK_SINGLE_OUTPUT"
    target = "task"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "task":
            return None
        task: TaskAsset = target["task"]
        outputs = sorted(task.output_tables)
        actual = f"实际产出={outputs}"
        return self.check(
            task.file,
            len(outputs) == 1,
            "Task必须有且只有一个持久产出表",
            target_type="task",
            expected="Task有且只有一个持久产出表",
            actual=actual,
            evidence={"outputs": outputs},
        )


class AssetTableSingleWriterRule(_AssetCompletenessRule):
    rule_id = "ASSET_TABLE_SINGLE_WRITER"
    target = "task"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "writer":
            return None
        writer_files = sorted(
            {
                file_name
                for files in target["writers_by_key"].values()
                for file_name in files
            }
        )
        actual = f"产出Task={writer_files}"
        return self.check(
            target["output"],
            len(target["writers_by_key"]) == 1,
            "目标表必须有且只有一个逻辑产出Task",
            expected="目标表有且只有一个逻辑产出Task",
            actual=actual,
            evidence={
                "writers": writer_files,
                "logical_writers": sorted(target["writers_by_key"]),
            },
        )


class AssetTaskLineageMatchesOutputRule(_AssetCompletenessRule):
    rule_id = "ASSET_TASK_LINEAGE_MATCHES_OUTPUT"
    target = "task"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["kind"] != "task":
            return None
        task: TaskAsset = target["task"]
        outputs = set(task.output_tables)
        lineage_targets = set(task.lineage_targets)
        actual = (
            f"实际产出={sorted(outputs)}，血缘目标={sorted(lineage_targets)}"
        )
        return self.check(
            task.file,
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


ASSET_COMPLETENESS_RULE_CLASSES = [
    AssetDdlHasModelRule,
    AssetExecutableDdlHasTaskRule,
    AssetModelHasDdlRule,
    AssetTaskOutputHasDdlRule,
    AssetTaskOutputHasModelRule,
    AssetTaskSingleOutputRule,
    AssetTableSingleWriterRule,
    AssetTaskLineageMatchesOutputRule,
]


def _asset_requires_task(
    asset: TableAsset,
    *,
    rule_context: dict,
) -> bool:
    if asset.layer.upper() == "ODS":
        return False
    table_identity = (
        asset.ddl.full_name
        if asset.ddl is not None and asset.ddl.full_name
        else asset.name
    )
    identity = table_identity_match_key(
        table_identity,
        default_catalog=rule_context.get("default_catalog", "internal"),
        default_db=rule_context.get("default_database", ""),
    )
    return identity not in rule_context.get(
        "external_taskless_identity_keys",
        frozenset(),
    )
