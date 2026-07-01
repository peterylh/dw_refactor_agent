"""Naming convention rule definitions."""

from __future__ import annotations

import json

from assess.project_facts.asset_catalog import (
    _display_file_path,
    _related_files_for_table,
)
from assess.project_facts.business_metadata import (
    _business_area_applies,
    _data_domain_applies,
)
from assess.project_facts.entity_metadata import (
    defined_entity_codes,
    grain_entity_codes,
    primary_entity_codes,
)
from assess.result_model import make_check
from assess.rules.engine.base import AssessRule
from assess.scoring.config import (
    FILE_RULE_DDL,
    FILE_RULE_MODEL_NAME,
    FILE_RULE_TASK_SQL,
)


class _NamingRule(AssessRule):
    dimension = "naming"
    domain = "table"
    target = "table"

    def check(
        self,
        *,
        target_type: str,
        target: str,
        passed: bool,
        expected,
        actual,
        target_detail: dict | None = None,
        evidence: dict,
        diagnostic: dict | None = None,
        summary: str = "",
        message: str,
        issue: dict | None,
        score_passed: int | None = None,
        score_total: int | None = None,
        fingerprint_discriminator: str = "",
    ) -> dict:
        check = make_check(
            rule_id=self.rule_id,
            target_type=target_type,
            target=target,
            passed=passed,
            expected=expected,
            actual=actual,
            target_detail=target_detail,
            evidence=evidence,
            diagnostic=diagnostic,
            summary=summary,
            message=message,
            issue=issue,
            fingerprint_discriminator=fingerprint_discriminator,
        )
        if score_passed is not None:
            check["_score_passed"] = score_passed
        if score_total is not None:
            check["_score_total"] = score_total
        return check


class NamingTableTemplateRule(_NamingRule):
    rule_id = "NAMING_TABLE_TEMPLATE"

    def evaluate(self, target: dict, rule_context: dict) -> dict:
        name = target["name"]
        layer = target["layer"]
        nc = rule_context["nc"]
        issue_context = _naming_issue_context(rule_context, name)
        valid = _check_table_name_any_template(name, layer, nc)
        model = dict((rule_context.get("models") or {}).get(name) or {})
        model.setdefault("name", name)
        model.setdefault("layer", layer)
        raw_diagnostic = _table_name_diagnostic(name, nc, model)
        violation = None
        if not valid:
            violation = {
                "code": "table_template",
                "rule_id": self.rule_id,
                "expected": "表名符合所在层级命名模板",
                "actual": name,
                "message": f"{name} 不符合 {layer} 层表名模板",
            }
        return self.check(
            target_type="table",
            target=name,
            passed=valid,
            target_detail=_table_target_detail(layer),
            expected=_expected_from_diagnostic(
                raw_diagnostic,
                description="表名符合所在层级命名模板",
                layer=layer,
            ),
            actual={"value": name},
            evidence=None,
            diagnostic=(
                None if valid else _diagnostic_from_diagnostic(raw_diagnostic)
            ),
            summary="表名不符合规范模板" if not valid else "表名符合规范模板",
            message="" if valid else violation["message"],
            issue=issue_context if violation else None,
            score_passed=int(valid),
            score_total=1,
        )


class NamingTableMaxLengthRule(_NamingRule):
    rule_id = "NAMING_TABLE_MAX_LENGTH"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        name = target["name"]
        layer = target["layer"]
        nc = rule_context["nc"]
        max_length = _table_name_max_length(name, layer, nc)
        if max_length is None:
            return None
        issue_context = _naming_issue_context(rule_context, name)
        length_ok = _check_table_name_length(name, layer, nc)
        violation = None
        if not length_ok:
            diagnostic = {
                "code": "max_length_exceeded",
                "actual_length": len(name),
                "max_length": max_length,
            }
            violation = {
                "code": "table_max_length",
                "rule_id": self.rule_id,
                "expected": f"表名长度 <= {max_length}",
                "actual": {"name": name, "length": len(name)},
                "message": f"表名长度 {len(name)} 超过配置上限 {max_length}",
            }
        return self.check(
            target_type="table",
            target=name,
            passed=length_ok,
            target_detail=_table_target_detail(layer),
            expected={
                "description": "表名长度不超过配置上限",
                "max_length": max_length,
            },
            actual={"value": name, "length": len(name)},
            evidence=None,
            diagnostic=None if length_ok else diagnostic,
            summary="表名超过长度限制"
            if not length_ok
            else "表名长度符合限制",
            message="" if length_ok else violation["message"],
            issue=issue_context if violation else None,
            score_passed=int(length_ok),
            score_total=1,
        )


class NamingColumnNameRule(_NamingRule):
    rule_id = "NAMING_COLUMN_NAME"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        name = target["name"]
        layer = target["layer"]
        nc = rule_context["nc"]
        metric_columns = set(
            _atomic_metric_names_for_table(target, rule_context["models"])
        ) | set(
            _derived_metric_names_for_table(target, rule_context["models"])
        )
        checks = []
        issue_context = _naming_issue_context(rule_context, name)
        for column in target.get("columns") or []:
            column_name = column["name"]
            if column_name in metric_columns:
                continue
            ok, _matched = _check_column_name(column_name, nc)
            raw_diagnostic = _column_name_diagnostic(column_name, nc)
            checks.append(
                self.check(
                    target_type="column",
                    target=column_name,
                    target_detail=_column_target_detail(
                        name,
                        column_name,
                        layer,
                    ),
                    passed=ok,
                    expected=_expected_from_diagnostic(
                        raw_diagnostic,
                        description="非指标字段符合字段命名规则",
                        layer=layer,
                    ),
                    actual={"value": column_name},
                    evidence=None,
                    diagnostic=(
                        None
                        if ok
                        else _diagnostic_from_diagnostic(raw_diagnostic)
                    ),
                    summary=("字段名符合规范" if ok else "字段名不符合规范"),
                    message=(f"不合规字段: {column_name}" if not ok else ""),
                    issue=issue_context if not ok else None,
                    score_passed=int(ok),
                    score_total=1,
                    fingerprint_discriminator=(f"column:{name}.{column_name}"),
                )
            )
        return checks


class NamingAtomicMetricRule(_NamingRule):
    rule_id = "NAMING_ATOMIC_METRIC"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        if not rule_context["atomic_rule_name"]:
            return []
        name = target["name"]
        layer = target["layer"]
        issue_context = _naming_issue_context(rule_context, name)
        checks = []
        for metric_name in _atomic_metric_names_for_table(
            target, rule_context["models"]
        ):
            rule_name = rule_context["atomic_rule_name"]
            raw_diagnostic = _metric_name_diagnostic(
                metric_name,
                rule_context["nc"],
                rule_name,
            )
            failed = not _check_atomic_metric_name(
                metric_name, rule_context["nc"]
            )
            checks.append(
                self.check(
                    target_type="metric",
                    target=metric_name,
                    target_detail=_metric_target_detail(
                        name,
                        metric_name,
                        layer,
                    ),
                    passed=not failed,
                    expected=_expected_from_diagnostic(
                        raw_diagnostic,
                        description="原子指标符合指标命名规则",
                        layer=layer,
                    ),
                    actual={"value": metric_name},
                    evidence=None,
                    diagnostic=(
                        None
                        if not failed
                        else _diagnostic_from_diagnostic(raw_diagnostic)
                    ),
                    summary=(
                        "原子指标命名合规"
                        if not failed
                        else "原子指标命名不合规"
                    ),
                    message=(
                        f"不合规原子指标: {metric_name}" if failed else ""
                    ),
                    issue=issue_context if failed else None,
                    score_passed=0 if failed else 1,
                    score_total=1,
                    fingerprint_discriminator=f"metric:{name}.{metric_name}",
                )
            )
        return checks


class NamingDerivedMetricRule(_NamingRule):
    rule_id = "NAMING_DERIVED_METRIC"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        if not rule_context["derived_rule_name"]:
            return []
        name = target["name"]
        layer = target["layer"]
        issue_context = _naming_issue_context(rule_context, name)
        checks = []
        for metric_name in _derived_metric_names_for_table(
            target, rule_context["models"]
        ):
            rule_name = rule_context["derived_rule_name"]
            raw_diagnostic = _metric_name_diagnostic(
                metric_name,
                rule_context["nc"],
                rule_name,
            )
            failed = not _check_derived_metric_name(
                metric_name, rule_context["nc"]
            )
            checks.append(
                self.check(
                    target_type="metric",
                    target=metric_name,
                    target_detail=_metric_target_detail(
                        name,
                        metric_name,
                        layer,
                    ),
                    passed=not failed,
                    expected=_expected_from_diagnostic(
                        raw_diagnostic,
                        description="派生指标符合指标命名规则",
                        layer=layer,
                    ),
                    actual={"value": metric_name},
                    evidence=None,
                    diagnostic=(
                        None
                        if not failed
                        else _diagnostic_from_diagnostic(raw_diagnostic)
                    ),
                    summary=(
                        "派生指标命名合规"
                        if not failed
                        else "派生指标命名不合规"
                    ),
                    message=(
                        f"不合规派生指标: {metric_name}" if failed else ""
                    ),
                    issue=issue_context if failed else None,
                    score_passed=0 if failed else 1,
                    score_total=1,
                    fingerprint_discriminator=f"metric:{name}.{metric_name}",
                )
            )
        return checks


class NamingDwsEntityAlignmentRule(_NamingRule):
    rule_id = "NAMING_DWS_ENTITY_ALIGNMENT"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        name = target["name"]
        layer = target["layer"]
        if not _check_table_name_any_template(name, layer, rule_context["nc"]):
            return None
        check_result = _score_dws_entity_name(
            name,
            layer,
            rule_context["nc"],
            rule_context["models"],
        )
        if check_result.get("total", 0) <= 0:
            return None
        violations = check_result.get("violations") or []
        return self.check(
            target_type="table",
            target=name,
            passed=not violations,
            target_detail=_table_target_detail(layer),
            expected={
                "description": "DWS表名实体包含于grain.entities",
            },
            actual={"violations": violations},
            evidence=None,
            diagnostic=None
            if not violations
            else {
                "code": "dws_entity_alignment_mismatch",
                "violations": violations,
            },
            summary=(
                "DWS表名实体与grain.entities一致"
                if not violations
                else "DWS表名实体与grain.entities不一致"
            ),
            message="; ".join(violations) if violations else "",
            issue=_naming_issue_context(rule_context, name)
            if violations
            else None,
            score_passed=check_result["passed"],
            score_total=check_result["total"],
        )


class NamingDimEntityAlignmentRule(_NamingRule):
    rule_id = "NAMING_DIM_ENTITY_ALIGNMENT"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        name = target["name"]
        layer = target["layer"]
        if not _check_table_name_any_template(name, layer, rule_context["nc"]):
            return None
        check_result = _score_dim_entity_name(
            name,
            layer,
            rule_context["nc"],
            rule_context["models"],
        )
        if check_result.get("total", 0) <= 0:
            return None
        violations = check_result.get("violations") or []
        return self.check(
            target_type="table",
            target=name,
            passed=not violations,
            target_detail=_table_target_detail(layer),
            expected={
                "description": "DIM表名实体等于主实体",
            },
            actual={"violations": violations},
            evidence=None,
            diagnostic=None
            if not violations
            else {
                "code": "dim_entity_alignment_mismatch",
                "violations": violations,
            },
            summary=(
                "DIM表名实体与主实体一致"
                if not violations
                else "DIM表名实体与主实体不一致"
            ),
            message="; ".join(violations) if violations else "",
            issue=_naming_issue_context(rule_context, name)
            if violations
            else None,
            score_passed=check_result["passed"],
            score_total=check_result["total"],
        )


class NamingDimClassificationAlignmentRule(_NamingRule):
    rule_id = "NAMING_DIM_CLASSIFICATION_ALIGNMENT"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        name = target["name"]
        layer = target["layer"]
        if not _check_table_name_any_template(name, layer, rule_context["nc"]):
            return None
        check_result = _score_dim_classification_name(
            name,
            layer,
            rule_context["nc"],
            rule_context["models"],
        )
        if check_result.get("total", 0) <= 0:
            return None
        violations = check_result.get("violations") or []
        return self.check(
            target_type="table",
            target=name,
            passed=not violations,
            target_detail=_table_target_detail(layer),
            expected={
                "description": "DIM表名分类段与模型元数据一致",
            },
            actual={"violations": violations},
            evidence=None,
            diagnostic=None
            if not violations
            else {
                "code": "dim_classification_alignment_mismatch",
                "violations": violations,
            },
            summary=(
                "DIM表名分类段与模型元数据一致"
                if not violations
                else "DIM表名分类段与模型元数据不一致"
            ),
            message="; ".join(violations) if violations else "",
            issue=_naming_issue_context(rule_context, name)
            if violations
            else None,
            score_passed=check_result["passed"],
            score_total=check_result["total"],
        )


class NamingSemanticMetadataAlignmentRule(_NamingRule):
    rule_id = "NAMING_SEMANTIC_METADATA_ALIGNMENT"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        name = target["name"]
        layer = target["layer"]
        table_name_valid = _check_table_name_any_template(
            name,
            layer,
            rule_context["nc"],
        )
        check_result, _summary = _score_table_semantic_metadata(
            name,
            layer,
            table_name_valid,
            rule_context,
        )
        if check_result.get("total", 0) <= 0:
            return None
        violations = check_result.get("violations") or []
        return self.check(
            target_type="table",
            target=name,
            passed=not violations,
            target_detail=_table_target_detail(layer),
            expected={
                "description": "表名语义段与模型元数据一致",
            },
            actual={"violations": violations},
            evidence=None,
            diagnostic=None
            if not violations
            else {
                "code": "semantic_metadata_alignment_mismatch",
                "violations": violations,
            },
            summary=(
                "表名语义段与模型元数据一致"
                if not violations
                else "表名语义段与模型元数据不一致"
            ),
            message="; ".join(violations) if violations else "",
            issue=_naming_issue_context(rule_context, name)
            if violations
            else None,
            score_passed=check_result["passed"],
            score_total=check_result["total"],
        )


class _NamingFileRule(_NamingRule):
    domain = "asset"
    target = "file"

    def evaluate(self, target: dict, rule_context: dict) -> dict:
        return self.check_file(**target)

    def check_file(
        self,
        *,
        display_file: str,
        expected: str,
        actual_display: str,
        passed: bool,
        rule_name: str,
    ) -> dict:
        check = make_check(
            rule_id=self.rule_id,
            target_type="file",
            target=display_file,
            passed=passed,
            expected={
                "description": rule_name,
                "value": expected,
            },
            actual={"value": actual_display},
            diagnostic=None
            if passed
            else {
                "code": "file_name_mismatch",
                "expected": expected,
                "actual": actual_display,
            },
            summary=rule_name if passed else f"{rule_name}不一致",
            message="" if passed else f"{rule_name}不一致",
            issue={
                "remediation": {
                    "related_files": [display_file],
                }
            }
            if not passed
            else None,
        )
        check["_score_passed"] = int(passed)
        check["_score_total"] = 1
        return check


class NamingDdlFileNameRule(_NamingFileRule):
    rule_id = "NAMING_DDL_FILE_NAME"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        ddl = target.get("ddl")
        if not ddl:
            return None
        return self.check_file(
            display_file=_display_file_path(
                rule_context["project_dir"],
                ddl["path"],
            ),
            expected=ddl["file_stem"],
            actual_display=ddl["declared_name"],
            passed=ddl["file_stem"] == ddl["declared_name"],
            rule_name=FILE_RULE_DDL,
        )


class NamingModelFileNameRule(_NamingFileRule):
    rule_id = "NAMING_MODEL_FILE_NAME"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        model = target.get("model")
        if not model or not model.get("path"):
            return None
        return self.check_file(
            display_file=_display_file_path(
                rule_context["project_dir"],
                model["path"],
            ),
            expected=model["file_stem"],
            actual_display=model["declared_name"],
            passed=model["file_stem"] == model["declared_name"],
            rule_name=FILE_RULE_MODEL_NAME,
        )


class NamingTaskOutputNameRule(_NamingFileRule):
    rule_id = "NAMING_TASK_OUTPUT_NAME"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        task = target.get("task")
        if not task:
            return None
        output_tables = task["output_tables"]
        actual_display = (
            ", ".join(sorted(str(item) for item in output_tables)) or "未解析"
        )
        return self.check_file(
            display_file=_display_file_path(
                rule_context["project_dir"],
                task["path"],
            ),
            expected=task["expected_table"],
            actual_display=actual_display,
            passed=output_tables == {task["expected_table"]},
            rule_name=FILE_RULE_TASK_SQL,
        )


NAMING_RULE_CLASSES = [
    NamingTableTemplateRule,
    NamingTableMaxLengthRule,
    NamingColumnNameRule,
    NamingAtomicMetricRule,
    NamingDerivedMetricRule,
    NamingDwsEntityAlignmentRule,
    NamingDimEntityAlignmentRule,
    NamingDimClassificationAlignmentRule,
    NamingSemanticMetadataAlignmentRule,
    NamingDdlFileNameRule,
    NamingModelFileNameRule,
    NamingTaskOutputNameRule,
]

NAMING_RULE_CLASSES_BY_ID = {
    rule_class.rule_id: rule_class for rule_class in NAMING_RULE_CLASSES
}


def _check_table_name_any_template(name: str, layer: str, nc) -> bool:
    ldef = nc.layers.get(layer)
    if not ldef:
        return False
    for segs in ldef.templates:
        if nc._match_segments(name, segs) is not None:
            return True
    return False


def _table_name_diagnostic(name: str, nc, model: dict | None) -> dict:
    if hasattr(nc, "diagnose_table_name"):
        return nc.diagnose_table_name(name, model)
    return {
        "actual": name,
        "layer": (model or {}).get("layer"),
        "layer_source": "model",
        "model_name": (model or {}).get("name"),
        "passed": False,
        "message": "命名配置对象不支持结构化诊断",
    }


def _table_target_detail(layer: str) -> dict:
    return {"layer": layer}


def _column_target_detail(
    table_name: str, column_name: str, layer: str
) -> dict:
    return {
        "table": table_name,
        "qualified_name": f"{table_name}.{column_name}",
        "layer": layer,
    }


def _metric_target_detail(
    table_name: str, metric_name: str, layer: str
) -> dict:
    return {
        "table": table_name,
        "qualified_name": f"{table_name}.{metric_name}",
        "layer": layer,
    }


def _attempt_rule_name(attempt: dict) -> str:
    rule = attempt.get("rule") or {}
    return str(rule.get("name") or "")


def _attempt_expected(attempt: dict) -> dict:
    rule = attempt.get("rule") or {}
    expected = {
        "rule_name": rule.get("name"),
        "description": rule.get("description"),
        "raw_expr": rule.get("raw_expr"),
        "constraints": rule.get("constraints") or {},
        "expression": attempt.get("expression"),
        "segments": attempt.get("segments") or [],
        "nodes": attempt.get("nodes") or [],
    }
    if attempt.get("model_constraints"):
        expected["model_constraints"] = attempt["model_constraints"]
    return {
        key: value
        for key, value in expected.items()
        if value not in (None, "", [])
    }


def _diagnostic_failure_from_attempt(attempt: dict) -> dict | None:
    if attempt.get("failure"):
        return attempt["failure"]
    for constraint in (attempt.get("model_constraints") or {}).values():
        failure = constraint.get("model_value_failure")
        if failure:
            return failure
    return None


def _diagnostic_code(
    raw_diagnostic: dict, default: str = "match_failed"
) -> str:
    failure = raw_diagnostic.get("failure")
    if failure and failure.get("code"):
        return str(failure["code"])
    for attempt in raw_diagnostic.get("attempts") or []:
        if attempt.get("passed"):
            continue
        failure = _diagnostic_failure_from_attempt(attempt)
        if failure and failure.get("code"):
            return str(failure["code"])
    return default


def _expected_from_diagnostic(
    raw_diagnostic: dict,
    *,
    description: str,
    layer: str | None = None,
) -> dict:
    attempts = raw_diagnostic.get("attempts") or []
    expected = {
        "description": description,
        "rule_names": [
            name
            for name in (_attempt_rule_name(attempt) for attempt in attempts)
            if name
        ],
        "attempts": [_attempt_expected(attempt) for attempt in attempts],
    }
    if layer:
        expected["layer"] = layer
    failure = raw_diagnostic.get("failure")
    if failure:
        expected["failure"] = failure
    return expected


def _diagnostic_from_diagnostic(raw_diagnostic: dict) -> dict:
    diagnostic = {
        "code": _diagnostic_code(raw_diagnostic),
        "attempts": raw_diagnostic.get("attempts") or [],
    }
    if raw_diagnostic.get("failure"):
        diagnostic["failure"] = raw_diagnostic["failure"]
    return diagnostic


def _table_name_max_length(name: str, layer: str, nc) -> int | None:
    if hasattr(nc, "table_max_length_for"):
        return nc.table_max_length_for(name, layer)
    return getattr(nc, "table_name_max_length", None)


def _check_table_name_length(name: str, layer: str, nc) -> bool:
    max_length = _table_name_max_length(name, layer, nc)
    return max_length is None or len(name) <= max_length


def _check_column_name(col_name: str, nc) -> tuple[bool, list[str]]:
    if col_name in nc.common_columns:
        return True, ["通用列名"]

    templates = getattr(nc, "column_templates", None) or (
        [nc.column_segments] if getattr(nc, "column_segments", None) else []
    )
    for template in templates:
        if nc._match_segments(col_name, template) is not None:
            return True, ["字段命名模板"]

    if templates:
        return False, []

    # OR 匹配：字段只要匹配任意一个已知后缀/前缀模式即合规
    matched = []
    sf = nc.types.get("suffix_field")
    if sf and sf.allow:
        for v in sorted(sf.allow, key=len, reverse=True):
            if col_name.endswith(f"_{v}"):
                matched.append(f"后缀 _{v}")
                break
    if not matched:
        pf = nc.types.get("prefix_field")
        if pf and pf.allow:
            for v in sorted(pf.allow, key=len, reverse=True):
                if col_name.startswith(f"{v}_"):
                    matched.append(f"前缀 {v}_")
                    break

    return bool(matched), matched


def _column_name_diagnostic(col_name: str, nc) -> dict:
    if hasattr(nc, "diagnose_column_name"):
        return nc.diagnose_column_name(col_name)
    return {
        "actual": col_name,
        "passed": False,
        "message": "命名配置对象不支持结构化诊断",
    }


def _metric_node_expected(nc, node: dict) -> dict:
    expected = dict(node)
    type_name = node.get("name") if node.get("kind") == "type" else ""
    if type_name:
        type_def = getattr(nc, "types", {}).get(type_name)
        if type_def:
            expected["type"] = {
                "name": type_name,
                "label": type_def.label,
                "description": type_def.desc,
                "allow": type_def.allow,
                "patterns": type_def.patterns,
                "dictionary": type_def.dictionary,
                "values_from": type_def.values_from,
            }
    return expected


def _metric_rule_label_for_name(nc, rule_name: str) -> str:
    labels = getattr(nc, "metric_rule_labels", {}) or {}
    return labels.get(rule_name, rule_name)


def _metric_name_diagnostic(metric_name: str, nc, rule_name: str) -> dict:
    attempts = []
    for rule_def in (getattr(nc, "metric_rules", {}) or {}).get(rule_name, []):
        kind = rule_def.get("kind")
        if kind == "segments":
            attempts.append(
                nc.diagnose_segments(
                    metric_name,
                    rule_def["template"],
                    {
                        "name": rule_name,
                        "description": _metric_rule_label_for_name(
                            nc,
                            rule_name,
                        ),
                        "raw_expr": rule_def.get("raw_expr"),
                        "constraints": {},
                    },
                )
            )
            continue
        if kind == "sequence":
            matched = nc._match_metric_sequence(
                metric_name,
                rule_def["nodes"],
                (),
            )
            attempt = {
                "actual": metric_name,
                "passed": matched is not None,
                "rule": {
                    "name": rule_name,
                    "description": _metric_rule_label_for_name(
                        nc,
                        rule_name,
                    ),
                    "raw_expr": rule_def.get("raw_expr"),
                    "constraints": {},
                },
                "nodes": [
                    _metric_node_expected(nc, node)
                    for node in rule_def.get("nodes") or []
                ],
            }
            if matched is not None:
                attempt["matched_values"] = matched
            else:
                attempt["failure"] = {
                    "code": "metric_sequence_mismatch",
                    "expected": attempt["nodes"],
                    "actual": metric_name,
                }
            attempts.append(attempt)
            continue
        attempts.append(
            {
                "actual": metric_name,
                "passed": False,
                "rule": {"name": rule_name},
                "failure": {
                    "code": "unsupported_metric_rule_kind",
                    "actual": kind,
                },
            }
        )

    if not attempts:
        return {
            "actual": metric_name,
            "passed": False,
            "attempts": [],
            "failure": {
                "code": "unknown_metric_rule",
                "actual": rule_name,
            },
        }

    return {
        "actual": metric_name,
        "passed": any(attempt.get("passed") for attempt in attempts),
        "attempts": attempts,
    }


def _as_string_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item or "").strip()]


def _dws_name_entities(name: str, nc) -> list[str]:
    return _table_name_type_values(
        name,
        "DWS",
        nc,
        "GRAIN_ENTITY",
        fallback_type_name="ENTITY",
    )


def _table_name_type_values(
    name: str,
    layer: str,
    nc,
    type_name: str,
    *,
    fallback_type_name: str | None = None,
) -> list[str]:
    layer_def = getattr(nc, "layers", {}).get("DWS")
    if layer != "DWS":
        layer_def = getattr(nc, "layers", {}).get(layer)
    if not layer_def:
        return []
    for segments in layer_def.templates:
        matched = nc._match_segments(name, segments)
        if matched is not None:
            values = _as_string_list(matched.get(type_name))
            if values:
                return values
            if fallback_type_name:
                return _as_string_list(matched.get(fallback_type_name))
    return []


def _model_grain_entities(
    table_name: str,
    model_metadata: dict | None,
) -> list[str]:
    if not model_metadata:
        return []
    return grain_entity_codes(model_metadata.get(table_name, {}))


def _model_defined_entities(model_metadata: dict | None) -> set[str]:
    return defined_entity_codes(model_metadata)


def _score_dws_entity_name(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
) -> dict:
    result = _naming_check_result(0, 0, [])
    if layer != "DWS":
        return result
    if not model_metadata or table_name not in model_metadata:
        return result

    expected = _model_grain_entities(table_name, model_metadata)
    if not expected:
        return result

    actual = _dws_name_entities(table_name, nc)
    result["total"] = 1
    violations = []
    if not actual or not set(actual).issubset(set(expected)):
        violations.append(f"表名ENTITY={actual}，grain.entities={expected}")

    if not violations:
        result["passed"] = 1
    else:
        result["violations"] = violations
    return result


def _score_dim_entity_name(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
) -> dict:
    result = _naming_check_result(0, 0, [])
    if layer != "DIM":
        return result
    if not model_metadata or table_name not in model_metadata:
        return result

    expected = _model_entity_codes(model_metadata.get(table_name))
    if not expected:
        result["total"] = 1
        result["violations"] = [
            "缺少entities.primary.code，无法检测DIM表名ENTITY"
        ]
        return result

    actual = _table_name_type_values(
        table_name,
        layer,
        nc,
        "MODEL_ENTITY",
        fallback_type_name="ENTITY",
    )
    result["total"] = 1
    if actual == expected:
        result["passed"] = 1
    else:
        result["violations"] = [
            f"表名MODEL_ENTITY={actual}，entities.primary.code={expected}"
        ]
    return result


def _score_dim_classification_name(
    table_name: str,
    layer: str,
    nc,
    model_metadata: dict | None,
) -> dict:
    result = _naming_check_result(0, 0, [])
    if layer != "DIM":
        return result
    if not model_metadata or table_name not in model_metadata:
        return result

    actual_role = _table_name_type_values(table_name, layer, nc, "DIM_ROLE")
    actual_content_type = _table_name_type_values(
        table_name,
        layer,
        nc,
        "DIM_CONTENT_TYPE",
    )
    if not actual_role and not actual_content_type:
        return result

    metadata = model_metadata.get(table_name) or {}
    expected_role = str(metadata.get("dimension_role") or "").strip().upper()
    expected_content_type = (
        str(metadata.get("dimension_content_type") or "").strip().upper()
    )

    result["total"] = 1
    violations = []
    if not expected_role:
        violations.append("缺少model.dimension_role，无法检测DIM表名角色")
    elif actual_role != [expected_role]:
        violations.append(
            f"表名DIM_ROLE={actual_role}，model.dimension_role={expected_role}"
        )

    if not expected_content_type:
        violations.append(
            "缺少model.dimension_content_type，无法检测DIM表名内容形态"
        )
    elif actual_content_type != [expected_content_type]:
        violations.append(
            f"表名DIM_CONTENT_TYPE={actual_content_type}，"
            f"model.dimension_content_type={expected_content_type}"
        )

    if not violations:
        result["passed"] = 1
    else:
        result["violations"] = violations
    return result


def _model_entity_codes(metadata: dict | None) -> list[str]:
    return primary_entity_codes(metadata)


def _table_column_names(table: dict) -> set[str]:
    return {
        str(column.get("name") or "").strip()
        for column in table.get("columns", []) or []
        if str(column.get("name") or "").strip()
    }


def _sort_naming_violations(violations: list) -> list:
    return sorted(
        violations,
        key=lambda item: (
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            if isinstance(item, dict)
            else str(item)
        ),
    )


def _naming_check_result(
    passed: int,
    total: int,
    violations: list,
    diagnostics: list | None = None,
) -> dict:
    result = {
        "passed": passed,
        "total": total,
        "violations": _sort_naming_violations(violations),
    }
    if diagnostics:
        result["diagnostics"] = sorted(
            diagnostics,
            key=lambda item: str(item.get("actual", "")),
        )
    return result


def _metric_rule_name(nc, *rule_names: str) -> str | None:
    metric_rules = getattr(nc, "metric_rules", {}) or {}
    for rule_name in rule_names:
        if metric_rules.get(rule_name):
            return rule_name
    return None


def _metric_rule_label(nc, fallback: str, rule_name: str | None) -> str:
    if not rule_name:
        return fallback
    labels = getattr(nc, "metric_rule_labels", {}) or {}
    return labels.get(rule_name) or fallback


def _check_atomic_metric_name(metric_name: str, nc) -> bool:
    rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    if not rule_name:
        return True
    return nc.match_metric_rule(metric_name, rule_name) is not None


def _check_derived_metric_name(metric_name: str, nc) -> bool:
    rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    if not rule_name:
        return False
    return nc.match_metric_rule(metric_name, rule_name) is not None


def _type_def_valid(nc, type_name: str, value: str) -> bool:
    type_def = getattr(nc, "types", {}).get(type_name)
    return type_def.validate(value) if type_def else True


def _metric_names_from_raw(raw_metrics) -> list[str]:
    if not isinstance(raw_metrics, list):
        return []

    names = []
    for metric in raw_metrics:
        if isinstance(metric, dict):
            name = str(metric.get("name") or "").strip()
        else:
            name = str(metric or "").strip()
        if name:
            names.append(name)
    return names


def _atomic_metric_names_for_table(
    table: dict,
    model_metadata: dict | None,
) -> list[str]:
    raw_metrics = table.get("atomic_metrics")
    if raw_metrics is None and model_metadata:
        metadata = model_metadata.get(table["name"], {})
        raw_metrics = metadata.get("atomic_metrics")
    return _metric_names_from_raw(raw_metrics)


def _derived_metric_names_for_table(
    table: dict,
    model_metadata: dict | None,
) -> list[str]:
    raw_metrics = table.get("derived_metrics")
    if raw_metrics is None and model_metadata:
        metadata = model_metadata.get(table["name"], {})
        raw_metrics = metadata.get("derived_metrics")
    return _metric_names_from_raw(raw_metrics)


def _valid_business_metadata_value(
    metadata: dict,
    field_name: str,
    type_name: str,
    nc,
    business_domain_config,
) -> str:
    raw_value = metadata.get(field_name)
    if raw_value in (None, "") or not business_domain_config:
        return ""
    if field_name == "data_domain":
        normalized = business_domain_config.normalize_domain(raw_value)
        in_dictionary = business_domain_config.is_valid_domain(normalized)
    else:
        normalized = business_domain_config.normalize_business_area(raw_value)
        in_dictionary = business_domain_config.is_valid_business_area(
            normalized
        )
    if not in_dictionary or not _type_def_valid(nc, type_name, normalized):
        return ""
    return normalized


def _score_table_semantic_metadata(
    table_name: str,
    layer: str,
    table_name_valid: bool,
    context: dict,
) -> tuple[dict, list[tuple[str, int, int]]]:
    result = _naming_check_result(0, 0, [])
    summary_checks = []
    if not table_name_valid:
        return result, summary_checks

    metadata = context["models"].get(table_name)
    business_config = context["business_domain_config"]
    if not isinstance(metadata, dict) or not business_config:
        return result, summary_checks

    checks = [
        (
            _data_domain_applies(layer),
            "data_domain",
            "DATA_DOMAIN_ID",
            "表名DATA_DOMAIN_ID与model.data_domain一致",
        ),
        (
            _business_area_applies(layer),
            "business_area",
            "BUSINESS_AREA_CODE",
            "表名BUSINESS_AREA_CODE与model.business_area一致",
        ),
    ]
    violations = []
    passed = 0
    total = 0
    for applies, field_name, type_name, rule_name in checks:
        if not applies:
            continue
        expected = _valid_business_metadata_value(
            metadata,
            field_name,
            type_name,
            context["nc"],
            business_config,
        )
        if not expected:
            continue
        actual = _table_name_type_values(
            table_name,
            layer,
            context["nc"],
            type_name,
        )
        ok = actual == [expected]
        total += 1
        passed += int(ok)
        summary_checks.append((rule_name, int(ok), 1))
        if not ok:
            violations.append(
                f"表名{type_name}={actual}，model.{field_name}={expected}"
            )

    return _naming_check_result(passed, total, violations), summary_checks


def _naming_issue_context(context: dict, table: str) -> dict:
    related_files = _related_files_for_table(context["assets"], table)
    return (
        {
            "remediation": {
                "related_files": related_files,
            }
        }
        if related_files
        else {}
    )


def _naming_violation_evidence(
    violation: dict | None,
    default: dict,
) -> dict:
    if not violation:
        return default
    evidence = dict(default)
    evidence.update(violation.get("evidence") or {})
    return evidence
