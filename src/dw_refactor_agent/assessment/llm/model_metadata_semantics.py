#!/usr/bin/env python3
"""模型元数据的 grain/entity 发现与项目级语义协调逻辑。"""

from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.table_inspector import (
    TableInspectResult,
    validate_inspection_result,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    legacy_entity_from_entities,
    legacy_related_entities_from_entities,
    normalize_entities,
)

DDL_NON_COLUMN_PREFIXES = {
    "AGGREGATE",
    "CREATE",
    "DISTRIBUTED",
    "DUPLICATE",
    "ENGINE",
    "KEY",
    "PARTITION",
    "PARTITIONED",
    "PRIMARY",
    "PROPERTIES",
    "UNIQUE",
}


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    value = str(value or "").strip()
    return [value] if value else []


def _is_time_grain_key(key: str, time_column: str = "") -> bool:
    key_lower = str(key or "").strip().lower()
    if not key_lower:
        return True
    if time_column and key_lower == str(time_column).strip().lower():
        return True
    return any(
        token in key_lower
        for token in (
            "date",
            "day",
            "dt",
            "hour",
            "month",
            "period",
            "quarter",
            "time",
            "week",
            "year",
        )
    )


def _grain_key_entity_pairs(
    grain: dict[str, Any], entities: list[dict[str, Any]] | None = None
) -> list[tuple[str, str]]:
    if not isinstance(grain, dict):
        return []
    grain_entities = _as_string_list(grain.get("entities"))
    if entities:
        if not grain_entities:
            return []
        pairs = []
        wanted = {entity.casefold() for entity in grain_entities}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            code = str(entity.get("code") or "").strip()
            if code.casefold() not in wanted:
                continue
            for key in _as_string_list(entity.get("key_columns")):
                pairs.append((key, code))
        return pairs

    keys = _as_string_list(grain.get("keys"))
    time_column = str(grain.get("time_column") or "")
    entity_keys = [
        key for key in keys if not _is_time_grain_key(key, time_column)
    ]
    if not entity_keys or not grain_entities:
        return []
    if len(grain_entities) == len(entity_keys):
        return list(zip(entity_keys, grain_entities))
    if len(grain_entities) == 1:
        return [(key, grain_entities[0]) for key in entity_keys]

    pairs = []
    for entity in grain_entities:
        entity_prefix = entity.lower()
        for key in entity_keys:
            if key.lower().startswith(entity_prefix):
                pairs.append((key, entity))
                break
    return pairs


def _build_grain_entity_index(
    results: list[TableInspectResult],
) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        if (
            result.status == "blocked"
            or result.table_type != "fact"
            or str(result.inferred_layer or "").upper() != "DWS"
        ):
            continue
        grouped: dict[str, dict[str, Any]] = {}
        for key, entity in _grain_key_entity_pairs(
            result.grain, result.entities
        ):
            entity_code = str(entity or "").strip()
            key_column = str(key or "").strip()
            if not entity_code or not key_column:
                continue
            canonical_code = entity_code.casefold()
            candidate = grouped.setdefault(
                canonical_code,
                {
                    "code": entity_code,
                    "key_columns": [],
                },
            )
            canonical_keys = {
                column.casefold() for column in candidate["key_columns"]
            }
            if key_column.casefold() not in canonical_keys:
                candidate["key_columns"].append(key_column)
        if grouped:
            index[result.table_name] = list(grouped.values())
    return index


def _column_comments_from_ddl(ddl: str) -> dict[str, str]:
    comments = {}
    for line in str(ddl or "").splitlines():
        name_match = re.match(r"\s*`?([A-Za-z_][A-Za-z0-9_]*)`?\s+", line)
        if not name_match:
            continue
        name = name_match.group(1)
        if name.upper() in DDL_NON_COLUMN_PREFIXES:
            continue
        comment_match = re.search(
            r"COMMENT\s+'([^']*)'", line, flags=re.IGNORECASE
        )
        comments[name] = (
            comment_match.group(1).strip() if comment_match else ""
        )
    return comments


def _entity_name_from_comment(comment: str) -> str:
    name = str(comment or "").strip()
    for suffix in ("ID", "Id", "id", "编号", "编码", "标识"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.strip()


def _related_entity_identity(
    item: dict[str, Any],
) -> tuple[str, tuple[str, ...]]:
    return (
        str(item.get("code") or "").strip(),
        tuple(_as_string_list(item.get("key_columns"))),
    )


def _merge_related_entities(
    current: list[dict[str, Any]], discovered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for item in current + discovered:
        if not isinstance(item, dict):
            continue
        identity = _related_entity_identity(item)
        if not identity[0] or not identity[1] or identity in seen:
            continue
        merged.append(item)
        seen.add(identity)
    return merged


def _canonical_table_reference(value: Any) -> str:
    text = str(value or "").strip().replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _split_column_reference(value: Any) -> tuple[str, str]:
    reference = _canonical_table_reference(value)
    if "." not in reference:
        return "", reference
    table_name, column_name = reference.rsplit(".", 1)
    return table_name, column_name


def _table_reference_matches(
    reference: str,
    table_name: str,
    context: TableContext,
) -> bool:
    wanted = _canonical_table_reference(reference)
    if not wanted:
        return False
    identity = _canonical_table_reference(context.table_identity)
    short_name = _canonical_table_reference(table_name).split(".")[-1]
    if "." in wanted and "." in identity:
        return (
            wanted == identity
            or wanted.endswith(f".{identity}")
            or identity.endswith(f".{wanted}")
        )
    return wanted.split(".")[-1] == short_name


def _context_for_table(
    contexts: dict[str, TableContext],
    table_name: str,
) -> TableContext | None:
    context = contexts.get(table_name)
    if context is not None:
        return context
    wanted = _canonical_table_reference(table_name)
    matches = [
        candidate
        for name, candidate in contexts.items()
        if _canonical_table_reference(name) == wanted
    ]
    return matches[0] if len(matches) == 1 else None


def _direct_grain_key_mapping(
    dimension_table: str,
    dimension_context: TableContext,
    grain_table: str,
    grain_context: TableContext,
    grain_keys: list[str],
    ddl_columns: dict[str, tuple[str, str]],
) -> tuple[str, ...]:
    source_columns = []
    for grain_key in grain_keys:
        matching_sources = set()
        wanted_key = grain_key.casefold()
        for edge in grain_context.column_lineage or []:
            if not isinstance(edge, dict):
                continue
            source_table, source_column = _split_column_reference(
                edge.get("source")
            )
            target_table, target_column = _split_column_reference(
                edge.get("target")
            )
            if (
                target_column != wanted_key
                or not _table_reference_matches(
                    target_table,
                    grain_table,
                    grain_context,
                )
                or not _table_reference_matches(
                    source_table,
                    dimension_table,
                    dimension_context,
                )
                or source_column not in ddl_columns
            ):
                continue
            matching_sources.add(source_column)
        if len(matching_sources) != 1:
            return ()
        source_columns.append(next(iter(matching_sources)))
    if len(set(source_columns)) != len(source_columns):
        return ()
    return tuple(source_columns)


def discover_related_entities_from_grain(
    result: TableInspectResult,
    context: TableContext | None,
    grain_entity_index: dict[str, list[dict[str, Any]]],
    contexts: dict[str, TableContext] | None = None,
) -> list[dict[str, Any]]:
    """从直接字段血缘证明的 DWS grain 反推维度表关联实体。"""
    if (
        result.table_type != "dimension"
        or not result.entity
        or not context
        or not contexts
    ):
        return []
    primary_code = str(result.entity.get("code") or "").strip()
    primary_keys = {
        key.casefold()
        for key in _as_string_list(result.entity.get("key_columns"))
    }
    if not primary_code or not primary_keys:
        return []

    comments_by_column = _column_comments_from_ddl(context.ddl)
    ddl_columns = {
        column.casefold(): (column, comment)
        for column, comment in comments_by_column.items()
    }
    mappings_by_code: dict[
        str,
        dict[frozenset[str], tuple[str, ...]],
    ] = {}
    display_codes = {}
    for grain_table, candidates in grain_entity_index.items():
        grain_context = _context_for_table(contexts, grain_table)
        if grain_context is None:
            continue
        for candidate in candidates:
            related_code = str(candidate.get("code") or "").strip()
            canonical_code = related_code.casefold()
            if not related_code or canonical_code == primary_code.casefold():
                continue
            mapping = _direct_grain_key_mapping(
                result.table_name,
                context,
                grain_table,
                grain_context,
                _as_string_list(candidate.get("key_columns")),
                ddl_columns,
            )
            if not mapping:
                continue
            display_codes.setdefault(canonical_code, related_code)
            mappings_by_code.setdefault(canonical_code, {}).setdefault(
                frozenset(mapping),
                mapping,
            )

    resolved_mappings = {
        code: next(iter(mappings.values()))
        for code, mappings in mappings_by_code.items()
        if len(mappings) == 1
    }
    codes_by_column: dict[str, set[str]] = {}
    for code, mappings in mappings_by_code.items():
        for key_columns in mappings.values():
            for key_column in key_columns:
                codes_by_column.setdefault(key_column, set()).add(code)

    discovered = []
    for canonical_code, key_columns in sorted(resolved_mappings.items()):
        if any(
            key_column in primary_keys
            or len(codes_by_column.get(key_column, set())) != 1
            for key_column in key_columns
        ):
            continue
        actual_columns = [ddl_columns[key][0] for key in key_columns]
        comment = next(
            (
                ddl_columns[key][1]
                for key in key_columns
                if ddl_columns[key][1]
            ),
            "",
        )
        discovered.append(
            {
                "code": display_codes[canonical_code],
                "name": _entity_name_from_comment(comment),
                "key_columns": actual_columns,
                "relationship": {
                    "type": "many_to_one",
                    "from_entity": primary_code,
                },
            }
        )
    return discovered


def enrich_results_with_related_entities(
    results: list[TableInspectResult], contexts: dict[str, TableContext]
) -> None:
    grain_entity_index = _build_grain_entity_index(results)
    for result in results:
        context = contexts.get(result.table_name)
        if not grain_entity_index:
            continue
        discovered = discover_related_entities_from_grain(
            result,
            context,
            grain_entity_index,
            contexts,
        )
        if discovered:
            result.resume_eligible = False
            result.related_entities = _merge_related_entities(
                result.related_entities,
                discovered,
            )
            result.entities = normalize_entities(
                result.entities,
                result.entity,
                result.related_entities,
            )


def enrich_results_with_project_semantics(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None = None,
) -> None:
    """Enrich related entities, then reconcile project-wide semantic codes."""
    enrich_results_with_related_entities(results, contexts)
    reconcile_project_semantics(results, contexts, catalog=catalog)
    _mark_composite_business_processes(results, contexts, catalog=catalog)
    promoted_results = [
        result
        for result in results
        if _promote_count_aggregates_to_atomic(result)
    ]
    if promoted_results:
        for result in promoted_results:
            context = _context_for_table(contexts, result.table_name)
            if context is not None:
                validate_inspection_result(result, context)
        _reconcile_business_processes(results, contexts, catalog=catalog)


def _promote_count_aggregates_to_atomic(
    result: TableInspectResult,
) -> bool:
    """Normalize target-grain row counts that do not have a base metric."""
    if (
        result.table_type != "fact"
        or str(result.inferred_layer or "").upper() != "DWS"
    ):
        return False
    promoted = []
    remaining = []
    atomic_names = {
        str(metric.get("name") or "").strip().casefold()
        for metric in result.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    for metric in result.derived_metrics:
        if (
            not isinstance(metric, dict)
            or str(metric.get("base_metric") or "").strip()
            or not _is_count_aggregate(metric.get("expression"))
        ):
            remaining.append(metric)
            continue
        name = str(metric.get("name") or "").strip()
        if not name:
            remaining.append(metric)
            continue
        normalized = {
            key: metric[key]
            for key in (
                "name",
                "data_type",
                "business_process",
                "action",
                "measure",
                "description",
                "reason",
                "confidence",
            )
            if key in metric
        }
        normalized["action"] = str(normalized.get("action") or "COUNT").strip()
        if name.casefold() not in atomic_names:
            result.columns.setdefault("atomic_metrics", []).append(normalized)
            atomic_names.add(name.casefold())
        promoted.append(name)
    if not promoted:
        return False

    result.columns["derived_metrics"] = remaining
    _remove_stale_metric_validation(result, promoted)
    result.resume_eligible = False
    message = (
        "semantic_reconciliation: promoted target-grain count aggregates "
        "to atomic metrics"
    )
    if message not in result.reasoning_steps:
        result.reasoning_steps.append(message)
    return True


def _is_count_aggregate(expression: Any) -> bool:
    text = str(expression or "").strip()
    if not text:
        return False
    try:
        parsed = sqlglot.parse_one(text, read="doris")
    except sqlglot.errors.SqlglotError:
        shorthand = re.fullmatch(
            r"(COUNT\s*\([^()]+\))\s+WHERE\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if shorthand is None:
            return False
        try:
            count = sqlglot.parse_one(shorthand.group(1), read="doris")
            predicate = sqlglot.parse_one(shorthand.group(2), read="doris")
        except sqlglot.errors.SqlglotError:
            return False
        forbidden_predicate_nodes = (
            exp.AggFunc,
            exp.Window,
            exp.Select,
            exp.Subquery,
        )
        return isinstance(count, exp.Count) and not any(
            predicate.find(node_type) is not None
            for node_type in forbidden_predicate_nodes
        )
    if isinstance(parsed, exp.Count):
        return True
    if not isinstance(parsed, exp.Sum) or not isinstance(
        parsed.this, exp.Case
    ):
        return False
    case = parsed.this
    values = [branch.args.get("true") for branch in case.args.get("ifs") or []]
    default = case.args.get("default")
    if default is not None:
        values.append(default)
    numeric_values = []
    for value in values:
        if not isinstance(value, exp.Literal) or value.is_string:
            return False
        try:
            numeric_values.append(float(value.this))
        except (TypeError, ValueError):
            return False
    return (
        bool(numeric_values)
        and 1.0 in numeric_values
        and set(numeric_values) <= {0.0, 1.0}
    )


def _remove_stale_metric_validation(
    result: TableInspectResult,
    metric_names: list[str],
) -> None:
    wanted = {name.casefold() for name in metric_names}
    validation = dict(result.validation or {})
    for key in (
        "missing_base_metrics",
        "missing_base_metric_tables",
        "invalid_base_metrics",
        "invalid_base_metric_tables",
        "ambiguous_base_metrics",
        "invalid_time_periods",
        "invalid_metric_expressions",
    ):
        remaining = [
            value
            for value in validation.get(key) or []
            if str(value).split(":", 1)[0].strip().casefold() not in wanted
        ]
        if remaining:
            validation[key] = remaining
        else:
            validation.pop(key, None)
    result.validation = validation


def reconcile_project_semantics(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None = None,
) -> None:
    """Reconcile only semantics supported by unique project-wide evidence."""
    _reconcile_dimension_entity_codes(
        results,
        contexts,
        catalog=catalog,
    )
    _reconcile_entity_codes(results, contexts)
    _reconcile_business_processes(results, contexts, catalog=catalog)


def _mark_composite_business_processes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None,
) -> None:
    """Mark DWS facts whose metrics are contributed by multiple sources."""
    established_codes = _catalog_code_lookup(catalog, "business_processes")
    for result in results:
        if (
            result.table_type != "fact"
            or str(result.inferred_layer or "").upper() != "DWS"
            or str(result.business_process or "").strip()
            or result.business_process_mode
        ):
            continue
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        evidence = _contributing_metric_source_evidence(
            result,
            context,
            results,
            contexts,
        )
        if len(evidence) < 2:
            continue
        process_evidence = []
        has_unconfirmed_source_process = False
        for _identity, source, metrics in evidence:
            source_process = str(source.business_process or "").strip()
            confirmed_process = established_codes.get(
                source_process.casefold()
            )
            if (
                source.table_type == "fact"
                and source.status != "blocked"
                and confirmed_process
            ):
                process_evidence.append((source, metrics, confirmed_process))
            elif source_process:
                has_unconfirmed_source_process = True
        if has_unconfirmed_source_process or not process_evidence:
            continue
        metric_process_evidence: dict[int, set[str]] = {}
        metrics_by_identity: dict[int, dict[str, Any]] = {}
        for _source, metrics, process in process_evidence:
            for metric in metrics:
                identity = id(metric)
                metrics_by_identity[identity] = metric
                metric_process_evidence.setdefault(identity, set()).add(
                    process
                )
        process_conflicts = []
        for identity, processes in metric_process_evidence.items():
            metric = metrics_by_identity[identity]
            current_process = str(metric.get("business_process") or "").strip()
            if current_process:
                processes.add(current_process)
            canonical_processes = {
                process.casefold() for process in processes if process
            }
            if len(canonical_processes) > 1:
                process_conflicts.append(str(metric.get("name") or "").strip())
                continue
            if not current_process and len(canonical_processes) == 1:
                metric["business_process"] = sorted(
                    processes,
                    key=lambda process: (process.casefold(), process),
                )[0]
        process_codes = {
            str(metric.get("business_process") or "").strip().casefold()
            for group in (
                result.atomic_metrics,
                result.derived_metrics,
                result.calculated_metrics,
            )
            for metric in group
            if isinstance(metric, dict)
            and str(metric.get("business_process") or "").strip()
        }
        if not process_codes and not process_conflicts:
            continue
        result.business_process_mode = "composite"
        result.business_process_sources = [
            identity for identity, _source, _metrics in evidence
        ]
        result.business_process_conflicts = sorted(
            {metric_name for metric_name in process_conflicts if metric_name},
            key=str.casefold,
        )
        result.resume_eligible = False
        result.validation = {
            key: values
            for key, values in (result.validation or {}).items()
            if key
            not in {
                "business_process_missing",
                "business_process_ambiguous",
            }
        }
        message = (
            "semantic_reconciliation: marked multi-source DWS as composite"
        )
        if message not in result.reasoning_steps:
            result.reasoning_steps.append(message)


def _contributing_metric_source_evidence(
    result: TableInspectResult,
    context: TableContext,
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[tuple[str, TableInspectResult, list[dict[str, Any]]]]:
    target_metrics = [
        metric
        for group in (
            result.atomic_metrics,
            result.derived_metrics,
            result.calculated_metrics,
        )
        for metric in group
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    ]
    metrics_by_name = {
        str(metric.get("name") or "").strip().casefold(): metric
        for metric in target_metrics
    }
    references: dict[str, list[dict[str, Any]]] = {}
    for metric in result.derived_metrics:
        if not isinstance(metric, dict):
            continue
        reference = str(metric.get("base_metric_table") or "").strip()
        if not reference or (
            not str(metric.get("base_metric") or "").strip()
            and not _is_count_aggregate(metric.get("expression"))
        ):
            continue
        references.setdefault(reference, []).append(metric)

    for edge in context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if (
            target_column not in metrics_by_name
            or (
                target_table
                and not _table_reference_matches(
                    target_table,
                    result.table_name,
                    context,
                )
            )
            or not source_table
        ):
            continue
        source = _result_for_table_reference(
            results,
            contexts,
            source_table,
        )
        if source is None:
            continue
        source_metric_names = {
            str(metric.get("name") or "").strip().casefold()
            for group in (
                source.atomic_metrics,
                source.derived_metrics,
                source.calculated_metrics,
            )
            for metric in group
            if isinstance(metric, dict)
            and str(metric.get("name") or "").strip()
        }
        if source_column not in source_metric_names:
            continue
        references.setdefault(source_table, []).append(
            metrics_by_name[target_column]
        )

    evidence = []
    seen_identities = set()
    for reference in sorted(references):
        source = _result_for_table_reference(results, contexts, reference)
        if source is None or source is result:
            continue
        source_context = _context_for_table(contexts, source.table_name)
        identity = (
            source_context.table_identity
            if source_context is not None and source_context.table_identity
            else source.table_name
        )
        if (
            identity
            and not _table_reference_matches(
                identity,
                result.table_name,
                context,
            )
            and identity.casefold() not in seen_identities
        ):
            metrics = list(
                {
                    id(metric): metric for metric in references[reference]
                }.values()
            )
            evidence.append((identity, source, metrics))
            seen_identities.add(identity.casefold())
    return sorted(evidence, key=lambda item: item[0].casefold())


def _reconcile_business_processes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None,
) -> None:
    established_codes = _catalog_code_lookup(
        catalog,
        "business_processes",
    )
    for _iteration in range(len(results) or 1):
        changed = False
        for result in results:
            if not _process_reconciliation_is_eligible(result):
                continue
            context = _context_for_table(contexts, result.table_name)
            if context is None:
                continue
            sources = _metric_process_source_results(
                result,
                context,
                results,
                contexts,
            )
            if len(sources) != 1:
                continue
            raw_source_processes = [
                str(source.business_process or "").strip()
                for source in sources
                if str(source.business_process or "").strip()
            ]
            if not raw_source_processes or any(
                process.casefold() not in established_codes
                for process in raw_source_processes
            ):
                continue
            source_processes = {
                established_codes[process.casefold()]
                for process in raw_source_processes
            }
            if len(source_processes) != 1:
                continue
            if str(
                result.inferred_layer or ""
            ).upper() == "DWD" and not _dwd_process_sources_are_equivalent(
                result,
                context,
                sources,
                contexts,
            ):
                continue
            canonical_process = _preferred_equivalent_code(
                next(iter(source_processes)),
                result.business_process,
                established_codes,
            )
            if not canonical_process:
                continue
            if _set_result_business_process(result, canonical_process):
                changed = True
        if not changed:
            break


def _process_reconciliation_is_eligible(
    result: TableInspectResult,
) -> bool:
    if result.table_type != "fact" or str(
        result.inferred_layer or ""
    ).upper() not in {"DWD", "DWS"}:
        return False
    if result.business_process_mode == "composite":
        return False
    blocking_keys = {
        key for key, values in (result.validation or {}).items() if values
    }
    return not blocking_keys or blocking_keys <= {
        "business_process_missing",
        "business_process_ambiguous",
    }


def _metric_process_source_results(
    result: TableInspectResult,
    context: TableContext,
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[TableInspectResult]:
    sources = []
    for _identity, source, _metrics in _contributing_metric_source_evidence(
        result,
        context,
        results,
        contexts,
    ):
        if source.table_type != "fact" or source.status == "blocked":
            return []
        if source not in sources:
            sources.append(source)
    references = {
        str(metric.get("base_metric_table") or "").strip()
        for metric in result.derived_metrics
        if isinstance(metric, dict)
        and str(metric.get("base_metric_table") or "").strip()
    }
    references.update(
        str(table_name).strip()
        for table_name, groups in (
            context.upstream_metric_groups or {}
        ).items()
        if any(groups.values())
    )
    for reference in sorted(references):
        source = _result_for_table_reference(
            results,
            contexts,
            reference,
        )
        if (
            source is None
            or source.table_type != "fact"
            or source.status == "blocked"
        ):
            return []
        if source not in sources:
            sources.append(source)
    return sources


def _dwd_process_sources_are_equivalent(
    result: TableInspectResult,
    context: TableContext,
    sources: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> bool:
    if (
        len(sources) != 1
        or result.derived_metrics
        or result.calculated_metrics
    ):
        return False
    if not _is_strict_row_preserving_select(context.etl_sql):
        return False
    source = sources[0]
    source_context = _context_for_table(contexts, source.table_name)
    if source_context is None:
        return False
    source_metrics = {
        str(metric.get("name") or "").strip().casefold()
        for metric in source.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    target_metrics = {
        str(metric.get("name") or "").strip().casefold()
        for metric in result.atomic_metrics
        if isinstance(metric, dict) and str(metric.get("name") or "").strip()
    }
    if not source_metrics or not target_metrics:
        return False
    source_primary = _single_primary_entity(source)
    target_primary = _single_primary_entity(result)
    if source_primary is None or target_primary is None:
        return False
    if (
        str(source_primary.get("code") or "").strip().casefold()
        != str(target_primary.get("code") or "").strip().casefold()
        or source.grain != result.grain
    ):
        return False
    source_keys = {
        key.casefold()
        for key in _as_string_list(source_primary.get("key_columns"))
    }
    target_keys = {
        key.casefold()
        for key in _as_string_list(target_primary.get("key_columns"))
    }
    if not source_keys or source_keys != target_keys:
        return False
    matched_targets = set()
    matched_target_keys = set()
    for edge in context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if not _table_reference_matches(
            source_table,
            source.table_name,
            source_context,
        ) or not _table_reference_matches(
            target_table,
            result.table_name,
            context,
        ):
            continue
        if source_column in source_metrics and target_column in target_metrics:
            matched_targets.add(target_column)
        if source_column in source_keys and target_column in target_keys:
            matched_target_keys.add(target_column)
    return (
        matched_targets == target_metrics
        and matched_target_keys == target_keys
    )


def _is_strict_row_preserving_select(sql_text: str) -> bool:
    if not str(sql_text or "").strip():
        return False
    try:
        statements = sqlglot.parse(sql_text, read="doris")
    except sqlglot.errors.SqlglotError:
        return False
    selects = [
        query
        for statement in statements
        for query in statement.find_all(exp.Select)
    ]
    if len(selects) != 1:
        return False
    query = selects[0]
    if any(
        query.args.get(key) is not None
        for key in (
            "where",
            "having",
            "qualify",
            "distinct",
            "group",
            "limit",
            "offset",
        )
    ):
        return False
    from_clause = query.args.get("from") or query.args.get("from_")
    source = getattr(from_clause, "this", None)
    allowed_table_args = {"this", "db", "catalog", "alias"}
    if (
        not isinstance(source, exp.Table)
        or any(
            value is not None and key not in allowed_table_args
            for key, value in source.args.items()
        )
        or query.args.get("laterals")
    ):
        return False
    return not any(
        query.find(node_type) is not None
        for node_type in (
            exp.AggFunc,
            exp.Join,
            exp.Lateral,
            exp.Pivot,
            exp.TableSample,
            exp.Unnest,
            exp.Window,
        )
    )


def _single_primary_entity(
    result: TableInspectResult,
) -> dict[str, Any] | None:
    primary = [
        entity
        for entity in result.entities
        if isinstance(entity, dict)
        and str(entity.get("type") or "").casefold() == "primary"
    ]
    return primary[0] if len(primary) == 1 else None


def _catalog_code_lookup(
    catalog: dict[str, Any] | None,
    section: str,
) -> dict[str, str]:
    entries = (
        (catalog or {}).get(section) or [] if isinstance(catalog, dict) else []
    )
    return {
        str(entry.get("code") or "").strip().casefold(): str(
            entry.get("code") or ""
        ).strip()
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("code") or "").strip()
    }


def _preferred_equivalent_code(
    source_code: str,
    target_code: str,
    established_codes: dict[str, str],
) -> str:
    candidates = {
        str(code or "").strip().casefold(): str(code or "").strip()
        for code in (source_code, target_code)
        if str(code or "").strip()
    }
    established = {
        canonical: established_codes[canonical]
        for canonical in candidates
        if canonical in established_codes
    }
    if len(established) > 1:
        return ""
    if established:
        return next(iter(established.values()))
    return str(source_code or "").strip()


def _set_result_business_process(
    result: TableInspectResult,
    process: str,
) -> bool:
    process = str(process or "").strip()
    if not process:
        return False
    changed = result.business_process != process
    result.business_process = process
    for group_name in (
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
    ):
        for metric in result.columns.get(group_name) or []:
            if not isinstance(metric, dict):
                continue
            if metric.get("business_process") != process:
                metric["business_process"] = process
                changed = True
    if changed:
        result.resume_eligible = False
        result.validation = {
            key: values
            for key, values in (result.validation or {}).items()
            if key
            not in {
                "business_process_missing",
                "business_process_ambiguous",
            }
        }
    return changed


def _reconcile_dimension_entity_codes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    *,
    catalog: dict[str, Any] | None,
) -> None:
    entries = _dimension_primary_entities(results, contexts)
    if len(entries) < 2:
        return
    established_codes = _catalog_code_lookup(catalog, "semantic_subjects")
    adjacency: dict[int, set[int]] = {
        index: set() for index in range(len(entries))
    }
    incoming: dict[int, set[int]] = {
        index: set() for index in range(len(entries))
    }
    for target_index, (
        target_table,
        target_context,
        target_primary,
    ) in enumerate(entries):
        for source_index, (
            source_table,
            source_context,
            source_primary,
        ) in enumerate(entries):
            if (
                source_index == target_index
                or not _dimension_key_lineage_matches(
                    target_table,
                    target_context,
                    target_primary,
                    source_table,
                    source_context,
                    source_primary,
                )
            ):
                continue
            adjacency[target_index].add(source_index)
            adjacency[source_index].add(target_index)
            incoming[target_index].add(source_index)

    unseen = set(adjacency)
    while unseen:
        seed = min(unseen)
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            for neighbor in adjacency[current] - component:
                component.add(neighbor)
                frontier.append(neighbor)
        unseen.difference_update(component)
        if len(component) < 2:
            continue
        component_codes = {
            str(entries[index][2].get("code") or "").strip().casefold(): str(
                entries[index][2].get("code") or ""
            ).strip()
            for index in component
            if str(entries[index][2].get("code") or "").strip()
        }
        established = {
            canonical: established_codes[canonical]
            for canonical in component_codes
            if canonical in established_codes
        }
        canonical_code = ""
        if len(established) == 1:
            canonical_code = next(iter(established.values()))
        elif not established:
            roots = [
                index
                for index in component
                if not (incoming[index] & component)
            ]
            root_codes = {
                str(entries[index][2].get("code") or "").strip()
                for index in roots
                if str(entries[index][2].get("code") or "").strip()
            }
            if len(root_codes) == 1:
                canonical_code = next(iter(root_codes))
        if not canonical_code:
            continue
        for index in component:
            table_name = entries[index][0]
            result = _result_for_table_reference(
                results,
                contexts,
                table_name,
            )
            if result is None:
                continue
            primary_indexes = [
                entity_index
                for entity_index, entity in enumerate(result.entities)
                if isinstance(entity, dict)
                and str(entity.get("type") or "").casefold() == "primary"
            ]
            if len(primary_indexes) != 1:
                continue
            primary_index = primary_indexes[0]
            if (
                str(
                    result.entities[primary_index].get("code") or ""
                ).casefold()
                != canonical_code.casefold()
            ):
                _apply_entity_code_replacements(
                    result,
                    {primary_index: canonical_code},
                )


def _dimension_key_lineage_matches(
    target_table: str,
    target_context: TableContext,
    target_primary: dict[str, Any],
    source_table: str,
    source_context: TableContext,
    source_primary: dict[str, Any],
) -> bool:
    upstream_matches = [
        upstream
        for upstream in target_context.upstream_tables or []
        if _table_reference_matches(upstream, source_table, source_context)
    ]
    if len(upstream_matches) != 1:
        return False
    target_keys = {
        key.casefold()
        for key in _as_string_list(target_primary.get("key_columns"))
    }
    source_keys = {
        key.casefold()
        for key in _as_string_list(source_primary.get("key_columns"))
    }
    if not target_keys or not source_keys:
        return False
    matched_targets = set()
    for edge in target_context.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        edge_source_table, source_column = _split_column_reference(
            edge.get("source")
        )
        edge_target_table, target_column = _split_column_reference(
            edge.get("target")
        )
        if (
            source_column in source_keys
            and target_column in target_keys
            and _table_reference_matches(
                edge_source_table,
                source_table,
                source_context,
            )
            and _table_reference_matches(
                edge_target_table,
                target_table,
                target_context,
            )
        ):
            matched_targets.add(target_column)
    return matched_targets == target_keys


def _reconcile_entity_codes(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> None:
    dimension_entities = _dimension_primary_entities(results, contexts)
    if not dimension_entities:
        return
    for result in results:
        if result.table_type == "dimension" or not result.entities:
            continue
        context = _context_for_table(contexts, result.table_name)
        proposals: dict[int, str] = {}
        for index, entity in enumerate(result.entities):
            if str(entity.get("type") or "").casefold() != "foreign":
                continue
            code = _canonical_entity_code_for_keys(
                result,
                context,
                entity,
                dimension_entities,
            )
            if (
                code
                and code.casefold() != str(entity.get("code") or "").casefold()
            ):
                proposals[index] = code
        proposed_counts: dict[str, int] = {}
        for code in proposals.values():
            canonical = code.casefold()
            proposed_counts[canonical] = proposed_counts.get(canonical, 0) + 1
        existing_codes = {
            str(entity.get("code") or "").casefold()
            for entity in result.entities
            if str(entity.get("code") or "").strip()
        }
        replacements = {
            index: code
            for index, code in proposals.items()
            if proposed_counts.get(code.casefold()) == 1
            and code.casefold() not in existing_codes
        }
        if replacements:
            _apply_entity_code_replacements(result, replacements)


def _dimension_primary_entities(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
) -> list[tuple[str, TableContext, dict[str, Any]]]:
    entries = []
    for result in results:
        if result.table_type != "dimension" or result.status == "blocked":
            continue
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        primary = [
            entity
            for entity in result.entities
            if isinstance(entity, dict)
            and str(entity.get("type") or "").casefold() == "primary"
        ]
        if len(primary) == 1:
            entries.append((result.table_name, context, primary[0]))
    return entries


def _dimension_key_code_index(
    entries: list[tuple[str, TableContext, dict[str, Any]]],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for _table_name, _context, entity in entries:
        code = str(entity.get("code") or "").strip()
        for key_column in _as_string_list(entity.get("key_columns")):
            key = key_column.casefold()
            if key not in {"id", "key", "code"}:
                index.setdefault(key, set()).add(code)
    return index


def _canonical_entity_code_for_keys(
    result: TableInspectResult,
    context: TableContext | None,
    entity: dict[str, Any],
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> str:
    key_columns = _as_string_list(entity.get("key_columns"))
    if not key_columns:
        return ""
    lineage_codes = _entity_codes_from_direct_lineage(
        result,
        context,
        key_columns,
        dimension_entities,
    )
    if len(lineage_codes) == 1:
        return next(iter(lineage_codes))
    reachable_dimension_entities = _direct_upstream_dimension_entities(
        context,
        dimension_entities,
    )
    key_code_index = _dimension_key_code_index(reachable_dimension_entities)
    key_code_sets = [
        key_code_index.get(key_column.casefold(), set())
        for key_column in key_columns
    ]
    if any(len(codes) != 1 for codes in key_code_sets):
        return ""
    key_codes = {next(iter(codes)) for codes in key_code_sets}
    return next(iter(key_codes)) if len(key_codes) == 1 else ""


def _direct_upstream_dimension_entities(
    context: TableContext | None,
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> list[tuple[str, TableContext, dict[str, Any]]]:
    if context is None:
        return []
    reachable = []
    for table_name, dimension_context, primary in dimension_entities:
        matches = [
            upstream_table
            for upstream_table in context.upstream_tables or []
            if _table_reference_matches(
                upstream_table,
                table_name,
                dimension_context,
            )
        ]
        if len(matches) == 1:
            reachable.append((table_name, dimension_context, primary))
    return reachable


def _entity_codes_from_direct_lineage(
    result: TableInspectResult,
    context: TableContext | None,
    key_columns: list[str],
    dimension_entities: list[tuple[str, TableContext, dict[str, Any]]],
) -> set[str]:
    if context is None:
        return set()
    codes_by_key: list[set[str]] = []
    for key_column in key_columns:
        matching_codes = set()
        for edge in context.column_lineage or []:
            if not isinstance(edge, dict):
                continue
            source_table, source_column = _split_column_reference(
                edge.get("source")
            )
            target_table, target_column = _split_column_reference(
                edge.get("target")
            )
            if (
                target_column != key_column.casefold()
                or not _table_reference_matches(
                    target_table,
                    result.table_name,
                    context,
                )
            ):
                continue
            for (
                dimension_table,
                dimension_context,
                primary,
            ) in dimension_entities:
                dimension_keys = {
                    key.casefold()
                    for key in _as_string_list(primary.get("key_columns"))
                }
                if (
                    source_column in dimension_keys
                    and _table_reference_matches(
                        source_table,
                        dimension_table,
                        dimension_context,
                    )
                ):
                    matching_codes.add(str(primary.get("code") or "").strip())
        if matching_codes:
            codes_by_key.append(matching_codes)
    if len(codes_by_key) != len(key_columns):
        return set()
    common_codes = set(codes_by_key[0])
    for codes in codes_by_key[1:]:
        common_codes.intersection_update(codes)
    return common_codes


def _apply_entity_code_replacements(
    result: TableInspectResult,
    replacements: dict[int, str],
) -> None:
    safe_replacements = {}
    for index, new_code in replacements.items():
        canonical_new = str(new_code or "").strip().casefold()
        conflicts = []
        for other_index, entity in enumerate(result.entities):
            if other_index == index:
                continue
            effective_code = replacements.get(
                other_index,
                str(entity.get("code") or "").strip(),
            )
            if str(effective_code or "").strip().casefold() == canonical_new:
                conflicts.append(other_index)
        if conflicts:
            message = (
                "semantic_reconciliation_skipped: canonical entity code "
                f"{new_code} already exists in {result.table_name}"
            )
            if message not in result.reasoning_steps:
                result.reasoning_steps.append(message)
            continue
        safe_replacements[index] = new_code
    if not safe_replacements:
        return
    result.resume_eligible = False
    old_to_new = {
        str(result.entities[index].get("code") or "").strip().casefold(): code
        for index, code in safe_replacements.items()
    }
    entities = []
    for index, entity in enumerate(result.entities):
        item = dict(entity)
        if index in safe_replacements:
            new_code = safe_replacements[index]
            item["code"] = new_code
        relationship = item.get("relationship")
        if isinstance(relationship, dict):
            relationship = dict(relationship)
            from_entity = str(relationship.get("from_entity") or "").casefold()
            if from_entity in old_to_new:
                relationship["from_entity"] = old_to_new[from_entity]
            item["relationship"] = relationship
        entities.append(item)
    result.entities = normalize_entities(entities)
    result.entity = legacy_entity_from_entities(result.entities)
    result.related_entities = legacy_related_entities_from_entities(
        result.entities
    )
    grain = dict(result.grain or {})
    grain["entities"] = [
        old_to_new.get(str(code).casefold(), code)
        for code in grain.get("entities") or []
    ]
    result.grain = grain


def _result_for_table_reference(
    results: list[TableInspectResult],
    contexts: dict[str, TableContext],
    reference: str,
) -> TableInspectResult | None:
    matches = []
    for result in results:
        context = _context_for_table(contexts, result.table_name)
        if context is None:
            continue
        if _table_reference_matches(reference, result.table_name, context):
            matches.append(result)
    return matches[0] if len(matches) == 1 else None
