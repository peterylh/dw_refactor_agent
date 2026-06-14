"""Naming convention scoring dimension."""

import json
from pathlib import Path

from assess.project_facts.asset_catalog import (
    _display_file_path,
    _related_files_for_table,
    _tables_for_naming,
    build_asset_catalog,
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
from assess.result_model import finalize_dimension, make_check
from assess.scoring.config import (
    ATOMIC_METRIC_RULE_NAME,
    BUSINESS_AREA_LAYERS,
    DATA_DOMAIN_LAYERS,
    DERIVED_METRIC_RULE_NAME,
    DIM_CLASSIFICATION_RULE_NAME,
    DIM_ENTITY_RULE_NAME,
    DWS_ENTITY_RULE_NAME,
    FILE_RULE_DDL,
    FILE_RULE_MODEL_NAME,
    FILE_RULE_TASK_SQL,
    NAMING_FILE_RULE_IDS,
    NAMING_RULES,
)


def _check_table_name_any_template(name: str, layer: str, nc) -> bool:
    ldef = nc.layers.get(layer)
    if not ldef:
        return False
    for segs in ldef.templates:
        if nc._match_segments(name, segs) is not None:
            return True
    return False


def _table_name_diagnostic(name: str, layer: str, nc) -> dict:
    if hasattr(nc, "diagnose_table_name"):
        return nc.diagnose_table_name(name, layer)
    return {
        "actual": name,
        "layer": layer,
        "passed": False,
        "message": "命名配置对象不支持结构化诊断",
    }


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


def _as_string_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [
        str(item).strip()
        for item in values
        if str(item or "").strip()
    ]


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
    expected_content_type = str(
        metadata.get("dimension_content_type") or "").strip().upper()

    result["total"] = 1
    violations = []
    if not expected_role:
        violations.append("缺少model.dimension_role，无法检测DIM表名角色")
    elif actual_role != [expected_role]:
        violations.append(
            f"表名DIM_ROLE={actual_role}，"
            f"model.dimension_role={expected_role}"
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

def _empty_file_score() -> dict:
    return dict(
        passed=0,
        total=0,
        checks=[],
    )


def _record_file_check(
    result: dict,
    rule: str,
    file_path: Path,
    project_dir: Path,
    expected: str,
    actual,
    passed: bool,
) -> None:
    result["total"] += 1
    if passed:
        result["passed"] += 1

    if isinstance(actual, (set, list, tuple)):
        actual_display = ", ".join(sorted(str(item) for item in actual)) or "未解析"
    else:
        actual_display = str(actual or "未解析")

    display_file = _display_file_path(project_dir, file_path)
    result["checks"].append(
        make_check(
            rule_id=NAMING_FILE_RULE_IDS[rule],
            target_type="file",
            target=display_file,
            passed=passed,
            expected=rule,
            actual=(
                "一致"
                if passed
                else f"期望: {expected} | 实际: {actual_display}"
            ),
            evidence={
                "file": display_file,
                "expected": expected,
                "actual": actual_display,
            },
            message="" if passed else f"{rule}不一致",
            issue={
                "remediation": {
                    "related_files": [display_file],
                }
            } if not passed else None,
        )
    )



def _score_file_naming_conventions(
    asset_catalog: dict,
) -> dict:
    project_dir = asset_catalog.get("project_dir")
    if not project_dir:
        return _empty_file_score()

    result = _empty_file_score()
    for asset in asset_catalog.get("tables", {}).values():
        ddl = asset.get("ddl")
        if ddl:
            _record_file_check(
                result,
                FILE_RULE_DDL,
                ddl["path"],
                project_dir,
                ddl["file_stem"],
                ddl["declared_name"],
                ddl["file_stem"] == ddl["declared_name"],
            )

        model = asset.get("model")
        if model and model.get("path"):
            _record_file_check(
                result,
                FILE_RULE_MODEL_NAME,
                model["path"],
                project_dir,
                model["file_stem"],
                model["declared_name"],
                model["file_stem"] == model["declared_name"],
            )

    for task in asset_catalog.get("tasks") or []:
        _record_file_check(
            result,
            FILE_RULE_TASK_SQL,
            task["path"],
            project_dir,
            task["expected_table"],
            task["output_tables"],
            task["output_tables"] == {task["expected_table"]},
        )

    return result


def _prepare_naming_context(
    tables: list,
    nc,
    model_metadata: dict | None,
    business_domain_config,
    project_dir: Path | None,
    edges: list | None,
    indirect_edges: list | None,
    asset_catalog: dict | None,
) -> dict:
    catalog = asset_catalog or build_asset_catalog(
        tables,
        model_metadata,
        project_dir,
        edges=edges,
        indirect_edges=indirect_edges,
    )
    if catalog.get("project_dir"):
        naming_tables = [
            dict(
                name=name,
                layer=asset.get("layer", "OTHER"),
                columns=asset.get("columns") or [],
            )
            for name, asset in catalog.get("tables", {}).items()
            if asset.get("ddl")
        ]
    else:
        naming_tables = _tables_for_naming(tables, None, model_metadata)

    atomic_rule_name = _metric_rule_name(nc, "atomic", "atomic_metrics")
    derived_rule_name = _metric_rule_name(nc, "derived", "derived_metrics")
    return dict(
        nc=nc,
        model_metadata=model_metadata or {},
        business_domain_config=business_domain_config,
        asset_catalog=catalog,
        middle=[
            table
            for table in naming_tables
            if table["layer"] in {"DWD", "DWS", "DIM"}
        ],
        atomic_rule_name=atomic_rule_name,
        derived_rule_name=derived_rule_name,
        atomic_rule_label=_metric_rule_label(
            nc,
            ATOMIC_METRIC_RULE_NAME,
            atomic_rule_name,
        ),
        derived_rule_label=_metric_rule_label(
            nc,
            DERIVED_METRIC_RULE_NAME,
            derived_rule_name,
        ),
    )


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

    metadata = context["model_metadata"].get(table_name)
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
                f"表名{type_name}={actual}，"
                f"model.{field_name}={expected}"
            )

    return _naming_check_result(passed, total, violations), summary_checks


def _score_middle_table(table: dict, context: dict) -> dict:
    nc = context["nc"]
    model_metadata = context["model_metadata"]
    name = table["name"]
    layer = table["layer"]
    columns = table.get("columns", [])
    summary_checks = []

    table_name_valid = _check_table_name_any_template(name, layer, nc)
    table_passed = int(table_name_valid)
    table_total = 1
    table_violations = []
    table_diagnostics = []
    if not table_name_valid:
        diagnostic = {
            "check": "table_template",
            **_table_name_diagnostic(name, layer, nc),
        }
        table_violations.append({
            "code": "table_template",
            "rule_id": "NAMING_TABLE_TEMPLATE",
            "expected": "表名符合所在层级命名模板",
            "actual": name,
            "message": f"{name} 不符合 {layer} 层表名模板",
            "evidence": diagnostic,
        })
        table_diagnostics.append(diagnostic)
    summary_checks.append(("表名符合规范模板", table_passed, 1))

    max_length = _table_name_max_length(name, layer, nc)
    if max_length is not None:
        length_ok = _check_table_name_length(name, layer, nc)
        table_total += 1
        table_passed += int(length_ok)
        summary_checks.append((
            f"表名长度 <= {max_length}",
            int(length_ok),
            1,
        ))
        if not length_ok:
            diagnostic = {
                "check": "table_max_length",
                "actual": name,
                "layer": layer,
                "passed": False,
                "expected": {"max_length": max_length},
                "actual_length": len(name),
            }
            table_violations.append({
                "code": "table_max_length",
                "rule_id": "NAMING_TABLE_MAX_LENGTH",
                "expected": f"表名长度 <= {max_length}",
                "actual": {
                    "name": name,
                    "length": len(name),
                },
                "message": f"表名长度 {len(name)} 超过配置上限 {max_length}",
                "evidence": diagnostic,
            })
            table_diagnostics.append(diagnostic)

    atomic_names = (
        _atomic_metric_names_for_table(table, model_metadata)
        if context["atomic_rule_name"]
        else []
    )
    atomic_violations = [
        metric for metric in atomic_names
        if not _check_atomic_metric_name(metric, nc)
    ]
    atomic_passed = len(atomic_names) - len(atomic_violations)
    if context["atomic_rule_name"]:
        summary_checks.append((
            context["atomic_rule_label"],
            atomic_passed,
            len(atomic_names),
        ))

    derived_names = (
        _derived_metric_names_for_table(table, model_metadata)
        if context["derived_rule_name"]
        else []
    )
    derived_violations = [
        metric for metric in derived_names
        if not _check_derived_metric_name(metric, nc)
    ]
    derived_passed = len(derived_names) - len(derived_violations)
    if context["derived_rule_name"]:
        summary_checks.append((
            context["derived_rule_label"],
            derived_passed,
            len(derived_names),
        ))

    metric_columns = set(atomic_names) | set(derived_names)
    column_violations = []
    column_diagnostics = []
    column_passed = 0
    column_total = 0
    for column in columns:
        column_name = column["name"]
        if column_name in metric_columns:
            continue
        column_total += 1
        ok, _matched = _check_column_name(column_name, nc)
        column_passed += int(ok)
        if not ok:
            column_violations.append(column_name)
            column_diagnostics.append(
                _column_name_diagnostic(column_name, nc)
            )
    summary_checks.append(("列名总计", column_passed, column_total))

    dws_entity_checks = (
        _score_dws_entity_name(
            name,
            layer,
            nc,
            model_metadata,
        )
        if table_name_valid
        else _naming_check_result(0, 0, [])
    )
    summary_checks.append((
        DWS_ENTITY_RULE_NAME,
        dws_entity_checks["passed"],
        dws_entity_checks["total"],
    ))
    dim_entity_checks = (
        _score_dim_entity_name(
            name,
            layer,
            nc,
            model_metadata,
        )
        if table_name_valid
        else _naming_check_result(0, 0, [])
    )
    summary_checks.append((
        DIM_ENTITY_RULE_NAME,
        dim_entity_checks["passed"],
        dim_entity_checks["total"],
    ))
    dim_classification_checks = (
        _score_dim_classification_name(
            name,
            layer,
            nc,
            model_metadata,
        )
        if table_name_valid
        else _naming_check_result(0, 0, [])
    )
    summary_checks.append((
        DIM_CLASSIFICATION_RULE_NAME,
        dim_classification_checks["passed"],
        dim_classification_checks["total"],
    ))
    semantic_checks, semantic_summary = _score_table_semantic_metadata(
        name,
        layer,
        table_name_valid,
        context,
    )
    summary_checks.extend(semantic_summary)

    passed = (
        table_passed
        + column_passed
        + atomic_passed
        + derived_passed
        + dws_entity_checks["passed"]
        + dim_entity_checks["passed"]
        + dim_classification_checks["passed"]
        + semantic_checks["passed"]
    )
    total = (
        table_total
        + column_total
        + len(atomic_names)
        + len(derived_names)
        + dws_entity_checks["total"]
        + dim_entity_checks["total"]
        + dim_classification_checks["total"]
        + semantic_checks["total"]
    )
    return dict(
        table=name,
        layer=layer,
        table_checks=_naming_check_result(
            table_passed,
            table_total,
            table_violations,
            table_diagnostics,
        ),
        column_checks=_naming_check_result(
            column_passed,
            column_total,
            column_violations,
            column_diagnostics,
        ),
        atomic_metric_checks=_naming_check_result(
            atomic_passed,
            len(atomic_names),
            atomic_violations,
        ),
        derived_metric_checks=_naming_check_result(
            derived_passed,
            len(derived_names),
            derived_violations,
        ),
        dws_entity_checks=dws_entity_checks,
        dim_entity_checks=dim_entity_checks,
        dim_classification_checks=dim_classification_checks,
        semantic_metadata_checks=semantic_checks,
        score=round(passed / total * 100, 1) if total else 100.0,
        _passed=passed,
        _total=total,
        _summary_checks=summary_checks,
    )


def _naming_issue_context(context: dict, table: str) -> dict:
    related_files = _related_files_for_table(context["asset_catalog"], table)
    return {
        "remediation": {
            "related_files": related_files,
        }
    } if related_files else {}


def _naming_violation_by_code(violations: list, code: str) -> dict | None:
    for violation in violations:
        if isinstance(violation, dict) and violation.get("code") == code:
            return violation
    return None


def _naming_violation_evidence(
    violation: dict | None,
    default: dict,
) -> dict:
    if not violation:
        return default
    evidence = dict(default)
    evidence.update(violation.get("evidence") or {})
    return evidence


def _build_naming_checks(
    table_results: list[dict],
    file_result: dict,
    context: dict,
) -> list[dict]:
    checks = []
    for result in table_results:
        table = result["table"]
        layer = result["layer"]
        issue_context = _naming_issue_context(context, table)

        table_violations = result["table_checks"]["violations"]
        template_violation = _naming_violation_by_code(
            table_violations,
            "table_template",
        )
        checks.append(
            make_check(
                rule_id="NAMING_TABLE_TEMPLATE",
                target_type="table",
                target=table,
                passed=template_violation is None,
                expected="表名符合所在层级命名模板",
                actual=(
                    "符合"
                    if template_violation is None
                    else template_violation["message"]
                ),
                evidence=_naming_violation_evidence(
                    template_violation,
                    {"layer": layer},
                ),
                message=(
                    template_violation["message"]
                    if template_violation else ""
                ),
                issue=issue_context if template_violation else None,
            )
        )

        if result["table_checks"]["total"] > 1:
            length_violation = _naming_violation_by_code(
                table_violations,
                "table_max_length",
            )
            checks.append(
                make_check(
                    rule_id="NAMING_TABLE_MAX_LENGTH",
                    target_type="table",
                    target=table,
                    passed=length_violation is None,
                    expected="表名长度不超过配置上限",
                    actual=(
                        f"长度={len(table)}"
                        if length_violation is None
                        else length_violation["message"]
                    ),
                    evidence=_naming_violation_evidence(
                        length_violation,
                        {"layer": layer, "actual_length": len(table)},
                    ),
                    message=(
                        length_violation["message"]
                        if length_violation else ""
                    ),
                    issue=issue_context if length_violation else None,
                )
            )

        column_checks = result.get("column_checks", {})
        if column_checks.get("total", 0) > 0:
            violations = column_checks.get("violations") or []
            checks.append(
                make_check(
                    rule_id="NAMING_COLUMN_NAME",
                    target_type="table",
                    target=table,
                    passed=not violations,
                    expected="所有非指标字段符合字段命名规则",
                    actual=(
                        "全部合规"
                        if not violations
                        else f"不合规字段: {violations}"
                    ),
                    evidence={
                        "layer": layer,
                        "violations": violations,
                        "checked_count": column_checks.get("total", 0),
                    },
                    message=(
                        f"不合规字段: {', '.join(violations)}"
                        if violations else ""
                    ),
                    issue=issue_context if violations else None,
                )
            )

        metric_specs = [
            (
                result.get("atomic_metric_checks", {}),
                "NAMING_ATOMIC_METRIC",
                "所有原子指标符合指标命名规则",
                "不合规原子指标",
                _atomic_metric_names_for_table(
                    {"name": table},
                    context["model_metadata"],
                ),
            ),
            (
                result.get("derived_metric_checks", {}),
                "NAMING_DERIVED_METRIC",
                "所有派生指标符合指标命名规则",
                "不合规派生指标",
                _derived_metric_names_for_table(
                    {"name": table},
                    context["model_metadata"],
                ),
            ),
        ]
        for check_result, rule_id, expected, label, metric_names in metric_specs:
            if check_result.get("total", 0) <= 0:
                continue
            violations = check_result.get("violations") or []
            for metric_name in metric_names:
                failed = metric_name in violations
                checks.append(
                    make_check(
                        rule_id=rule_id,
                        target_type="metric",
                        target=f"{table}.{metric_name}",
                        passed=not failed,
                        expected=expected,
                        actual=(
                            "合规"
                            if not failed
                            else f"{label}: {metric_name}"
                        ),
                        evidence={
                            "table": table,
                            "layer": layer,
                            "metric": metric_name,
                        },
                        message=f"{label}: {metric_name}" if failed else "",
                        issue=issue_context if failed else None,
                    )
                )

        alignment_specs = [
            (
                result.get("dws_entity_checks", {}),
                "NAMING_DWS_ENTITY_ALIGNMENT",
                "DWS表名实体包含于grain.entities",
            ),
            (
                result.get("dim_entity_checks", {}),
                "NAMING_DIM_ENTITY_ALIGNMENT",
                "DIM表名实体等于主实体",
            ),
            (
                result.get("dim_classification_checks", {}),
                "NAMING_DIM_CLASSIFICATION_ALIGNMENT",
                "DIM表名分类段与模型元数据一致",
            ),
            (
                result.get("semantic_metadata_checks", {}),
                "NAMING_SEMANTIC_METADATA_ALIGNMENT",
                "表名语义段与模型元数据一致",
            ),
        ]
        for check_result, rule_id, expected in alignment_specs:
            if check_result.get("total", 0) <= 0:
                continue
            violations = check_result.get("violations") or []
            checks.append(
                make_check(
                    rule_id=rule_id,
                    target_type="table",
                    target=table,
                    passed=not violations,
                    expected=expected,
                    actual="一致" if not violations else "; ".join(violations),
                    evidence={"layer": layer, "violations": violations},
                    message="; ".join(violations) if violations else "",
                    issue=issue_context if violations else None,
                )
            )

    checks.extend(file_result.get("checks") or [])
    return checks


def _build_final_naming_result(
    table_results: list[dict],
    file_result: dict,
    context: dict,
) -> dict:
    total_passed = sum(result["_passed"] for result in table_results)
    total_checks = sum(result["_total"] for result in table_results)
    total_passed += file_result["passed"]
    total_checks += file_result["total"]
    checks = _build_naming_checks(table_results, file_result, context)
    return finalize_dimension(
        dimension="naming",
        score=round(total_passed / total_checks * 100, 1)
        if total_checks else 100.0,
        checks=checks,
        rules=NAMING_RULES,
        summary={
            "file_checks": dict(
                passed=file_result["passed"],
                total=file_result["total"],
            ),
        },
    )


def score_naming_conventions(
    tables: list,
    nc,
    model_metadata: dict | None = None,
    business_domain_config=None,
    *,
    project_dir: Path | None = None,
    edges: list | None = None,
    indirect_edges: list | None = None,
    asset_catalog: dict | None = None,
) -> dict:
    context = _prepare_naming_context(
        tables,
        nc,
        model_metadata,
        business_domain_config,
        project_dir,
        edges,
        indirect_edges,
        asset_catalog,
    )
    table_results = [
        _score_middle_table(table, context)
        for table in context["middle"]
    ]
    file_result = _score_file_naming_conventions(
        context["asset_catalog"],
    )
    return _build_final_naming_result(
        table_results,
        file_result,
        context,
    )
