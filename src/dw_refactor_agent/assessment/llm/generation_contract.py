"""Deterministic cold-start execution inference and publication checks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp

from dw_refactor_agent.assessment.llm.inspection_contract import (
    business_process_codes,
    canonical_semantic_code,
)
from dw_refactor_agent.config import TEXT_ENCODING

DEFAULT_SLICE_PERIOD = "D"
REINSPECTION_ERROR_TYPES = frozenset(
    {
        "business_process_ambiguous",
        "business_process_missing",
        "business_process_unknown",
        "bridge_entities_invalid",
        "bridge_grain_invalid",
        "bridge_semantics_invalid",
        "dimension_primary_entity_invalid",
        "duplicate_entity_codes",
        "entity_key_missing",
        "entity_relationship_origin_missing",
        "entity_relationship_origin_unknown",
        "grain_column_missing",
        "grain_entity_unknown",
        "semantic_subject_missing",
        "semantic_subject_unknown",
    }
)


def _canonical_code(value: Any) -> str:
    return canonical_semantic_code(value)


def _task_facts(
    asset: dict[str, Any],
    *,
    full_refresh: bool,
) -> list[dict[str, Any]]:
    return [
        task
        for task in asset.get("tasks") or []
        if bool(task.get("is_full_refresh")) is full_refresh
    ]


def _task_sql(tasks: list[dict[str, Any]]) -> str:
    statements = []
    for task in tasks:
        path = task.get("path")
        if path:
            statements.append(Path(path).read_text(encoding=TEXT_ENCODING))
    return "\n".join(statements)


def _ddl_column_names(asset: dict[str, Any]) -> list[str]:
    return [
        str(column.get("name") or "").strip()
        for column in (asset.get("ddl") or {}).get("columns") or []
        if str(column.get("name") or "").strip()
    ]


def _ddl_column_type(
    asset: dict[str, Any],
    column_name: str,
) -> str:
    wanted = column_name.casefold()
    for column in (asset.get("ddl") or {}).get("columns") or []:
        if str(column.get("name") or "").strip().casefold() == wanted:
            return str(column.get("type") or "").strip()
    return ""


def _target_table_pattern(table_name: str) -> str:
    return (
        r"(?:`?[A-Za-z_][A-Za-z0-9_]*`?\.)*`?" + re.escape(table_name) + r"`?"
    )


def _has_target_truncate(table_name: str, task_sql: str) -> bool:
    return bool(
        re.search(
            rf"\bTRUNCATE\s+TABLE\s+"
            rf"{_target_table_pattern(table_name)}(?=\s|;|$)",
            task_sql,
            flags=re.IGNORECASE,
        )
    )


def _parameter_name(parameter: exp.Parameter) -> str:
    value = parameter.this
    if isinstance(value, exp.Var):
        return str(value.name or "").strip()
    return str(value or "").strip().lstrip("@")


def _temporal_evidence_period(
    value: str,
    *,
    is_type: bool = False,
) -> str:
    normalized = str(value or "").strip().casefold()
    tokens = set(re.findall(r"[a-z]+", normalized))
    if is_type and re.match(
        r"^(?:date|datetime|timestamp|time)(?:v2)?(?:\b|\s|\()",
        normalized,
    ):
        return DEFAULT_SLICE_PERIOD
    if "month" in tokens:
        return "M"
    if tokens & {
        "date",
        "datetime",
        "day",
        "period",
        "time",
        "timestamp",
        "week",
        "year",
    }:
        return DEFAULT_SLICE_PERIOD
    return ""


def _direct_temporal_parameter(
    projection: exp.Expression,
) -> tuple[str, str]:
    while isinstance(projection, (exp.Alias, exp.Paren)):
        projection = projection.this
    if isinstance(projection, exp.Parameter):
        return _parameter_name(projection), ""
    if isinstance(projection, exp.Cast):
        target_type = projection.args.get("to")
        target_sql = (
            target_type.sql(dialect="doris") if target_type is not None else ""
        )
        if isinstance(
            projection.this, exp.Parameter
        ) and _temporal_evidence_period(target_sql, is_type=True):
            return _parameter_name(projection.this), ""
        return "", ""
    if isinstance(projection, exp.TsOrDsToDate) and isinstance(
        projection.this,
        exp.Parameter,
    ):
        return _parameter_name(projection.this), ""
    if isinstance(projection, exp.TimeToStr) and isinstance(
        projection.this,
        exp.Parameter,
    ):
        format_expression = projection.args.get("format")
        if not isinstance(format_expression, exp.Literal):
            return "", ""
        date_format = str(format_expression.this or "").casefold()
        if "%y" not in date_format or "%m" not in date_format:
            return "", ""
        period = "D" if "%d" in date_format else "M"
        return _parameter_name(projection.this), period
    return "", ""


def _temporal_slice_period(
    column_name: str,
    column_type: str,
    parameter_name: str,
    expression_period: str,
) -> str:
    column_period = _temporal_evidence_period(column_name)
    if not column_period:
        column_period = _temporal_evidence_period(
            column_type,
            is_type=True,
        )
    parameter_period = _temporal_evidence_period(parameter_name)
    if not column_period or not parameter_period:
        return ""
    if expression_period:
        if expression_period != column_period:
            return ""
        if parameter_period != expression_period and expression_period != "M":
            return ""
        return expression_period
    return column_period if column_period == parameter_period else ""


def _insert_target(
    statement: exp.Insert,
) -> tuple[exp.Table | None, list[str]]:
    target = statement.this
    if isinstance(target, exp.Schema):
        table = target.this
        columns = [
            str(column.name or "").strip()
            for column in target.expressions
            if isinstance(column, exp.Identifier)
            and str(column.name or "").strip()
        ]
    else:
        table = target
        columns = []
    return (table if isinstance(table, exp.Table) else None), columns


def _query_selects(query: exp.Expression | None) -> list[exp.Select]:
    while isinstance(query, (exp.Paren, exp.Subquery)):
        query = query.this
    if isinstance(query, exp.Select):
        return [query]
    if not isinstance(query, exp.Union):
        return []
    selects = []
    for branch in (query.this, query.expression):
        while isinstance(branch, (exp.Paren, exp.Subquery)):
            branch = branch.this
        if isinstance(branch, exp.Select):
            selects.append(branch)
        elif isinstance(branch, exp.Union):
            selects.extend(_query_selects(branch))
        else:
            return []
    return selects


def _insert_selects(statement: exp.Insert) -> list[exp.Select]:
    return _query_selects(
        statement.args.get("expression") or statement.args.get("source")
    )


def _select_slice_binding(
    query: exp.Select,
    asset: dict[str, Any],
    target_columns: list[str],
) -> dict[str, str]:
    projections = list(query.expressions)
    if not target_columns or len(target_columns) != len(projections):
        return {}

    bindings = []
    for column_name, projection in zip(target_columns, projections):
        parameter_name, expression_period = _direct_temporal_parameter(
            projection
        )
        if not parameter_name:
            continue
        period = _temporal_slice_period(
            column_name,
            _ddl_column_type(asset, column_name),
            parameter_name,
            expression_period,
        )
        if not period:
            continue
        bindings.append(
            {
                "param": parameter_name,
                "column": column_name,
                "period": period,
            }
        )
    return bindings[0] if len(bindings) == 1 else {}


def _insert_slice_binding(
    statement: exp.Insert,
    asset: dict[str, Any],
    explicit_columns: list[str],
) -> dict[str, str]:
    target_columns = explicit_columns or _ddl_column_names(asset)
    bindings = [
        _select_slice_binding(query, asset, target_columns)
        for query in _insert_selects(statement)
    ]
    if not bindings or any(not binding for binding in bindings):
        return {}
    identities = {
        (
            binding["param"].casefold(),
            binding["column"].casefold(),
            binding["period"],
        )
        for binding in bindings
    }
    return bindings[0] if len(identities) == 1 else {}


def _target_overwrite_mode(
    table_name: str,
    task_sql: str,
) -> str:
    try:
        statements = sqlglot.parse(task_sql, dialect="doris")
    except Exception:
        return ""
    partitioned = False
    for statement in statements:
        if not isinstance(statement, exp.Insert) or not statement.args.get(
            "overwrite"
        ):
            continue
        target, _explicit_columns = _insert_target(statement)
        if target is None or target.name.casefold() != table_name.casefold():
            continue
        if target.args.get("partition") or statement.args.get("partition"):
            partitioned = True
        else:
            return "full"
    return "partitioned" if partitioned else ""


def _insert_projection_slice_binding(
    table_name: str,
    asset: dict[str, Any],
    task_sql: str,
) -> dict[str, str]:
    try:
        statements = sqlglot.parse(task_sql, dialect="doris")
    except Exception:
        return {}

    bindings = []
    matched_target = False
    for statement in statements:
        if not isinstance(statement, exp.Insert):
            continue
        target, explicit_columns = _insert_target(statement)
        if target is None or target.name.casefold() != table_name.casefold():
            continue
        matched_target = True
        binding = _insert_slice_binding(
            statement,
            asset,
            explicit_columns,
        )
        if not binding:
            return {}
        bindings.append(binding)
    if not matched_target:
        return {}
    identities = {
        (
            binding["param"].casefold(),
            binding["column"].casefold(),
            binding["period"],
        )
        for binding in bindings
    }
    return bindings[0] if len(identities) == 1 else {}


def _slice_binding(
    table_name: str,
    asset: dict[str, Any],
    task_sql: str,
) -> dict[str, str]:
    delete_pattern = re.compile(
        rf"\bDELETE\s+FROM\s+{_target_table_pattern(table_name)}"
        rf"\s+WHERE\s+(.*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for delete_match in delete_pattern.finditer(task_sql):
        predicate = delete_match.group(1)
        for column in sorted(
            _ddl_column_names(asset),
            key=len,
            reverse=True,
        ):
            binding = re.search(
                rf"(?<![A-Za-z0-9_`])"
                rf"(?:`?[A-Za-z_][A-Za-z0-9_]*`?\.)?`?"
                rf"{re.escape(column)}`?\s*=\s*"
                rf"(?:(?!\b(?:AND|OR)\b)[^;]){{0,120}}?"
                r"@([A-Za-z_][A-Za-z0-9_]*)",
                predicate,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not binding:
                continue
            period = DEFAULT_SLICE_PERIOD
            if "month" in column.lower() or "%y-%m" in predicate.lower():
                period = "M"
            return {
                "param": binding.group(1),
                "column": column,
                "period": period,
            }

    return _insert_projection_slice_binding(table_name, asset, task_sql)


def infer_execution_mapping(
    table_name: str,
    asset: dict[str, Any],
    *,
    layer: str,
) -> dict[str, Any]:
    """Infer an executable model contract from task SQL and asset facts."""
    main_tasks = _task_facts(asset, full_refresh=False)
    if not main_tasks:
        materialized = "incremental" if layer in {"DWD", "DWS"} else "full"
        execution = {"materialized": materialized}
        if materialized == "full":
            execution["full_refresh_strategy"] = "replace_all"
        return execution

    task_sql = _task_sql(main_tasks)
    overwrite_mode = _target_overwrite_mode(table_name, task_sql)
    if _has_target_truncate(table_name, task_sql) or overwrite_mode == "full":
        return {
            "materialized": "full",
            "full_refresh_strategy": "replace_all",
        }

    full_refresh_tasks = _task_facts(asset, full_refresh=True)
    execution = {
        "materialized": "incremental",
        "full_refresh_strategy": (
            "companion" if full_refresh_tasks else "replay_slices"
        ),
    }
    if overwrite_mode == "partitioned":
        return execution
    slice_config = _slice_binding(table_name, asset, task_sql)
    if slice_config:
        execution["slice"] = slice_config
    return execution


def _error(
    error_type: str,
    table_name: str,
    message: str,
) -> dict[str, str]:
    return {"type": error_type, "table": table_name, "message": message}


def _validate_execution(
    table_name: str,
    metadata: dict[str, Any],
    asset: dict[str, Any],
) -> list[dict[str, str]]:
    main_tasks = _task_facts(asset, full_refresh=False)
    if not main_tasks:
        layer = str(metadata.get("layer") or "").upper()
        if layer in {"DWD", "DWS"}:
            return [
                _error(
                    "execution_task_missing",
                    table_name,
                    f"{layer} execution cannot be inferred without task SQL",
                )
            ]
        return []

    execution = metadata.get("execution") or {}
    materialized = str(execution.get("materialized") or "").lower()
    strategy = str(execution.get("full_refresh_strategy") or "").lower()
    task_sql = _task_sql(main_tasks)
    has_truncate = _has_target_truncate(table_name, task_sql)
    overwrite_mode = _target_overwrite_mode(table_name, task_sql)
    if overwrite_mode == "partitioned":
        return [
            _error(
                "execution_partition_overwrite_unsupported",
                table_name,
                "partition INSERT OVERWRITE requires an explicit execution "
                "contract",
            )
        ]
    expected_materialized = (
        "full" if has_truncate or overwrite_mode == "full" else "incremental"
    )
    if materialized != expected_materialized:
        return [
            _error(
                "execution_materialized_mismatch",
                table_name,
                f"task SQL requires {expected_materialized}, got "
                f"{materialized or 'missing'}",
            )
        ]

    errors = []
    if materialized == "full":
        if strategy != "replace_all":
            errors.append(
                _error(
                    "execution_strategy_invalid",
                    table_name,
                    "full model requires full_refresh_strategy=replace_all",
                )
            )
        if execution.get("slice"):
            errors.append(
                _error(
                    "execution_slice_invalid",
                    table_name,
                    "full model cannot define execution.slice",
                )
            )
        return errors

    expected_strategy = (
        "companion"
        if _task_facts(asset, full_refresh=True)
        else "replay_slices"
    )
    if strategy != expected_strategy:
        errors.append(
            _error(
                "execution_strategy_invalid",
                table_name,
                f"incremental model requires {expected_strategy}, got "
                f"{strategy or 'missing'}",
            )
        )
    slice_config = execution.get("slice") or {}
    if not slice_config:
        strategy_label = f"{strategy} model" if strategy else "model"
        errors.append(
            _error(
                "execution_slice_missing",
                table_name,
                f"incremental {strategy_label} requires execution.slice",
            )
        )
        return errors
    for field in ("param", "column", "period"):
        if not str(slice_config.get(field) or "").strip():
            errors.append(
                _error(
                    "execution_slice_invalid",
                    table_name,
                    f"execution.slice.{field} is required",
                )
            )
    ddl_columns = {name.casefold() for name in _ddl_column_names(asset)}
    slice_column = str(slice_config.get("column") or "").strip()
    if slice_column and slice_column.casefold() not in ddl_columns:
        errors.append(
            _error(
                "execution_slice_column_missing",
                table_name,
                f"execution.slice.column={slice_column} is absent from DDL",
            )
        )
    return errors


def _catalog_has_code(
    catalog: dict[str, Any],
    section: str,
    code: str,
) -> bool:
    wanted = _canonical_code(code)
    return bool(
        wanted
        and any(
            isinstance(entry, dict)
            and _canonical_code(entry.get("code")) == wanted
            for entry in catalog.get(section) or []
        )
    )


def _validate_entities(
    table_name: str,
    metadata: dict[str, Any],
    asset: dict[str, Any],
) -> list[dict[str, str]]:
    errors = []
    entities = metadata.get("entities") or []
    canonical_codes = [
        _canonical_code(entity.get("code"))
        for entity in entities
        if isinstance(entity, dict) and entity.get("code")
    ]
    duplicate_codes = sorted(
        {code for code in canonical_codes if canonical_codes.count(code) > 1}
    )
    if duplicate_codes:
        errors.append(
            _error(
                "duplicate_entity_codes",
                table_name,
                "duplicate entities: " + ", ".join(duplicate_codes),
            )
        )

    ddl_columns = {name.casefold() for name in _ddl_column_names(asset)}
    entity_codes = {
        _canonical_code(entity.get("code"))
        for entity in entities
        if isinstance(entity, dict) and entity.get("code")
    }
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        code = str(entity.get("code") or "").strip() or "<missing>"
        key_columns = [
            str(column).strip()
            for column in entity.get("key_columns") or []
            if str(column).strip()
        ]
        if not key_columns:
            errors.append(
                _error(
                    "entity_key_missing",
                    table_name,
                    f"entity {code} requires at least one key column",
                )
            )
        for key_column in key_columns:
            if str(key_column).strip().casefold() not in ddl_columns:
                errors.append(
                    _error(
                        "entity_key_missing",
                        table_name,
                        f"entity {code} key {key_column} is absent from DDL",
                    )
                )
        relationship = entity.get("relationship") or {}
        entity_type = str(entity.get("type") or "").strip().lower()
        relationship_type = str(relationship.get("type") or "").strip()
        from_entity = str(relationship.get("from_entity") or "").strip()
        is_dimension = str(metadata.get("table_type") or "").lower() == (
            "dimension"
        )
        if (
            is_dimension
            and entity_type == "foreign"
            and (not relationship_type or not from_entity)
        ):
            errors.append(
                _error(
                    "entity_relationship_origin_missing",
                    table_name,
                    f"foreign entity {code} requires relationship.type and "
                    "relationship.from_entity",
                )
            )
        elif from_entity and _canonical_code(from_entity) not in entity_codes:
            errors.append(
                _error(
                    "entity_relationship_origin_unknown",
                    table_name,
                    f"entity {code} relationship.from_entity={from_entity} "
                    "is not declared",
                )
            )

    grain = metadata.get("grain") or {}
    for entity_code in grain.get("entities") or []:
        if _canonical_code(entity_code) not in entity_codes:
            errors.append(
                _error(
                    "grain_entity_unknown",
                    table_name,
                    f"grain entity {entity_code} is not declared",
                )
            )
    for column in grain.get("additional_key_columns") or []:
        if str(column).strip().casefold() not in ddl_columns:
            errors.append(
                _error(
                    "grain_column_missing",
                    table_name,
                    f"grain additional key {column} is absent from DDL",
                )
            )
    time_column = str(grain.get("time_column") or "").strip()
    if time_column and time_column.casefold() not in ddl_columns:
        errors.append(
            _error(
                "grain_column_missing",
                table_name,
                f"grain time_column={time_column} is absent from DDL",
            )
        )
    return errors


def _inspection_process_codes(inspection: dict[str, Any]) -> list[str]:
    columns = inspection.get("columns") or {}
    return business_process_codes(
        inspection.get("business_process"),
        (
            columns.get("atomic_metrics") or [],
            columns.get("derived_metrics") or [],
            columns.get("calculated_metrics") or [],
        ),
    )


def _validate_semantics(
    table_name: str,
    metadata: dict[str, Any],
    inspection: dict[str, Any] | None,
    catalog: dict[str, Any],
) -> list[dict[str, str]]:
    errors = []
    entities = metadata.get("entities") or []
    table_type = str(metadata.get("table_type") or "").lower()
    if inspection is not None and table_type == "dimension":
        primary_codes = [
            str(entity.get("code") or "").strip()
            for entity in entities
            if isinstance(entity, dict)
            and str(entity.get("type") or "").lower() == "primary"
        ]
        if len(primary_codes) != 1:
            errors.append(
                _error(
                    "dimension_primary_entity_invalid",
                    table_name,
                    "dimension requires exactly one primary entity",
                )
            )
        subject = str(metadata.get("semantic_subject") or "").strip()
        if len(primary_codes) == 1 and _canonical_code(
            subject
        ) != _canonical_code(primary_codes[0]):
            errors.append(
                _error(
                    "semantic_subject_missing",
                    table_name,
                    "semantic_subject must match the primary entity code",
                )
            )
        if subject and not _catalog_has_code(
            catalog, "semantic_subjects", subject
        ):
            errors.append(
                _error(
                    "semantic_subject_unknown",
                    table_name,
                    f"semantic_subject={subject} is absent from catalog",
                )
            )

    process = str(metadata.get("business_process") or "").strip()
    if table_type == "bridge":
        entity_codes = {
            _canonical_code(entity.get("code"))
            for entity in entities
            if isinstance(entity, dict) and entity.get("code")
        }
        if len(entity_codes) < 2:
            errors.append(
                _error(
                    "bridge_entities_invalid",
                    table_name,
                    "bridge model requires at least two distinct entities",
                )
            )
        grain_entities = {
            _canonical_code(code)
            for code in (metadata.get("grain") or {}).get("entities") or []
            if _canonical_code(code)
        }
        if entity_codes != grain_entities:
            errors.append(
                _error(
                    "bridge_grain_invalid",
                    table_name,
                    "bridge grain.entities must cover every entity",
                )
            )
        inspection_processes = (
            _inspection_process_codes(inspection)
            if inspection is not None
            else []
        )
        inspection_columns = (
            inspection.get("columns") or {} if inspection is not None else {}
        )
        has_metrics = any(
            metadata.get(group) or inspection_columns.get(group)
            for group in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            )
        )
        if process or inspection_processes or has_metrics:
            errors.append(
                _error(
                    "bridge_semantics_invalid",
                    table_name,
                    "bridge must not declare business process or metrics",
                )
            )
    if table_type == "fact":
        inspected_processes = (
            _inspection_process_codes(inspection)
            if inspection is not None
            else []
        )
        if inspection is None and not process:
            errors.append(
                _error(
                    "business_process_missing",
                    table_name,
                    "fact model requires exactly one business process",
                )
            )
        elif inspection is not None and not inspected_processes:
            errors.append(
                _error(
                    "business_process_missing",
                    table_name,
                    "fact inspection did not identify a business process",
                )
            )
        elif inspection is not None and len(inspected_processes) > 1:
            errors.append(
                _error(
                    "business_process_ambiguous",
                    table_name,
                    "fact inspection identified multiple business processes: "
                    + ", ".join(inspected_processes),
                )
            )
        elif (
            inspection is not None
            and _canonical_code(process) != inspected_processes[0]
        ):
            errors.append(
                _error(
                    "business_process_missing",
                    table_name,
                    "the inspected business process was not written to model",
                )
            )
    if process and not _catalog_has_code(
        catalog, "business_processes", process
    ):
        errors.append(
            _error(
                "business_process_unknown",
                table_name,
                f"business_process={process} is absent from catalog",
            )
        )
    return errors


def validate_generate_candidate(
    model_metadata: dict[str, dict[str, Any]],
    assets: dict[str, dict[str, Any]],
    *,
    llm_result: dict[str, Any] | None,
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Validate a complete candidate before generate replaces models."""
    errors = []
    inspections = {
        str(item.get("table_name") or "").casefold(): item
        for item in (llm_result or {}).get("tables") or []
        if isinstance(item, dict)
    }
    blocked_tables = sorted(
        str(inspection.get("table_name") or table_name)
        for table_name, inspection in inspections.items()
        if str(inspection.get("status") or "").lower() == "blocked"
    )
    for table_name in blocked_tables:
        errors.append(
            _error(
                "llm_inspection_blocked",
                table_name,
                "blocked inspection cannot be published by generate",
            )
        )

    blocked_table_keys = {
        table_name.casefold() for table_name in blocked_tables
    }
    if llm_result is not None:
        for table_name, metadata in sorted(model_metadata.items()):
            layer = str(metadata.get("layer") or "").upper()
            if (
                layer in {"DWD", "DWS", "DIM"}
                and table_name.casefold() not in inspections
            ):
                errors.append(
                    _error(
                        "llm_inspection_missing",
                        table_name,
                        "LLM generate requires inspection coverage for every "
                        "MID model",
                    )
                )

    for table_name, metadata in sorted(model_metadata.items()):
        asset = assets.get(table_name) or {}
        errors.extend(_validate_execution(table_name, metadata, asset))
        inspection = inspections.get(table_name.casefold())
        if inspection and table_name.casefold() not in blocked_table_keys:
            errors.extend(_validate_entities(table_name, metadata, asset))
            errors.extend(
                _validate_semantics(
                    table_name,
                    metadata,
                    inspection,
                    catalog,
                )
            )
        elif llm_result is None:
            errors.extend(
                _validate_semantics(
                    table_name,
                    metadata,
                    None,
                    catalog,
                )
            )
    reinspection_tables = sorted(
        {
            str(error.get("table") or "")
            for error in errors
            if error.get("type") in REINSPECTION_ERROR_TYPES
            and str(error.get("table") or "").casefold() in inspections
        },
        key=str.casefold,
    )
    return {
        "status": "blocked" if errors else "passed",
        "error_count": len(errors),
        "errors": errors,
        "blocked_tables": blocked_tables,
        "reinspection_tables": reinspection_tables,
    }
