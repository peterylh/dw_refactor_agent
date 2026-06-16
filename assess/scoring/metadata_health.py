"""Model metadata health scoring dimension."""

from __future__ import annotations

from assess.project_facts.business_metadata import (
    _business_area_applies,
    _data_domain_applies,
)
from assess.project_facts.entity_metadata import (
    defined_entity_codes,
    grain_key_columns,
    model_entities,
    primary_entity_codes,
)
from assess.result_model import finalize_dimension, make_check
from assess.scoring.config import METADATA_HEALTH_RULES, SEVERITY_LOW
from assess.scoring.utils import _as_string_list, _type_def_valid


def _model_defined_entities(model_metadata: dict | None) -> set[str]:
    return defined_entity_codes(model_metadata)


def _model_entity_codes(metadata: dict | None) -> list[str]:
    return primary_entity_codes(metadata)


def _table_column_names(table: dict) -> set[str]:
    return {
        str(column.get("name") or "").strip()
        for column in table.get("columns", []) or []
        if str(column.get("name") or "").strip()
    }


def score_metadata_health(
    tables: list,
    nc,
    model_metadata: dict | None,
    business_domain_config=None,
    *,
    asset_catalog: dict | None = None,
) -> dict:
    """检查 models/*.yaml 的结构自洽性与业务元数据有效性。"""
    if not model_metadata:
        return finalize_dimension(
            dimension="metadata_health",
            score=100.0,
            checks=[],
            rules=METADATA_HEALTH_RULES,
        )

    if asset_catalog:
        tables_by_name = {
            name: dict(
                name=name,
                layer=asset.get("layer", "OTHER"),
                columns=asset.get("columns") or [],
            )
            for name, asset in asset_catalog.get("tables", {}).items()
            if asset.get("ddl") or asset.get("lineage_table")
        }
    else:
        tables_by_name = {table["name"]: table for table in tables}
    defined_entities = _model_defined_entities(model_metadata)
    checks = []

    def record(
        table_name: str,
        rule_id: str,
        ok: bool,
        expected: str,
        actual: str,
        evidence: dict | None = None,
        reason: str = "",
        message: str = "",
        severity: str | None = None,
    ) -> None:
        issue = {}
        if reason:
            issue["message"] = message
        if severity:
            issue["severity"] = severity
        checks.append(
            make_check(
                rule_id=rule_id,
                target_type="table",
                target=table_name,
                passed=ok,
                expected=expected,
                actual=actual,
                evidence=evidence,
                message=message,
                issue=issue or None,
            )
        )

    for table_name, metadata in model_metadata.items():
        if not isinstance(metadata, dict):
            continue
        table = tables_by_name.get(table_name)
        columns = _table_column_names(table) if table else set()

        entities = model_entities(metadata)
        entity_codes = _model_entity_codes(metadata)
        primary_code = entity_codes[0] if entity_codes else ""
        layer = str(
            metadata.get("layer") or (table or {}).get("layer") or "OTHER"
        ).upper()
        if layer == "DIM":
            semantic_subject = str(
                metadata.get("semantic_subject") or ""
            ).strip()
            record(
                table_name,
                "METADATA_DIM_HAS_PRIMARY_ENTITY",
                bool(entity_codes),
                "DIM模型配置主实体编码",
                entity_codes[0] if entity_codes else "未配置",
                {"layer": layer},
                "missing",
                "缺少entities.primary.code",
            )
            record(
                table_name,
                "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY",
                bool(
                    semantic_subject
                    and primary_code
                    and semantic_subject == primary_code
                ),
                "semantic_subject等于DIM主实体编码",
                semantic_subject or "未配置",
                {
                    "layer": layer,
                    "semantic_subject": semantic_subject,
                    "primary_entity": primary_code,
                },
                "mismatch",
                (
                    "DIM模型缺少semantic_subject"
                    if not semantic_subject
                    else (
                        f"semantic_subject={semantic_subject}，"
                        f"primary_entity={primary_code or '未配置'}"
                    )
                ),
            )

        if table:
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                entity_code = str(entity.get("code") or "").strip()
                entity_type = str(entity.get("type") or "").strip().lower()
                key_columns = _as_string_list(entity.get("key_columns"))
                if key_columns:
                    missing_keys = [
                        key for key in key_columns if key not in columns
                    ]
                    record(
                        table_name,
                        "METADATA_ENTITY_KEYS_EXIST",
                        not missing_keys,
                        f"entities[{entity_code}].key_columns存在于表字段",
                        (
                            "全部存在"
                            if not missing_keys
                            else f"缺失字段: {missing_keys}"
                        ),
                        {
                            "entity": entity_code,
                            "key_columns": key_columns,
                            "table_columns": sorted(columns),
                        },
                        "",
                        (
                            f"entities[{entity_code}]"
                            f".key_columns不存在={missing_keys}"
                        ),
                    )
                if entity_type == "primary":
                    continue
                relationship = entity.get("relationship")
                if primary_code and isinstance(relationship, dict):
                    from_entity = str(
                        relationship.get("from_entity") or ""
                    ).strip()
                    record(
                        table_name,
                        "METADATA_RELATIONSHIP_FROM_PRIMARY",
                        from_entity == primary_code,
                        "relationship.from_entity等于主实体",
                        from_entity,
                        {
                            "entity": entity_code,
                            "primary_entity": primary_code,
                        },
                        "",
                        (
                            f"entities[{entity_code}]"
                            f".relationship.from_entity={from_entity}，"
                            f"primary_entity={primary_code}"
                        ),
                    )
                if primary_code and entity_code:
                    record(
                        table_name,
                        "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY",
                        entity_code != primary_code,
                        "关联实体code不同于主实体",
                        entity_code,
                        {
                            "entity": entity_code,
                            "primary_entity": primary_code,
                        },
                        "",
                        f"entities.code={entity_code} 与主实体重复",
                    )

        grain = metadata.get("grain")
        if table and isinstance(grain, dict):
            grain_keys = grain_key_columns(metadata)
            if grain_keys:
                missing_grain_keys = [
                    key for key in grain_keys if key not in columns
                ]
                record(
                    table_name,
                    "METADATA_GRAIN_KEYS_EXIST",
                    not missing_grain_keys,
                    "grain.keys存在于表字段",
                    (
                        "全部存在"
                        if not missing_grain_keys
                        else f"缺失字段: {missing_grain_keys}"
                    ),
                    {
                        "grain_keys": grain_keys,
                        "table_columns": sorted(columns),
                    },
                    "",
                    f"grain.keys不存在={missing_grain_keys}",
                )

        grain_entities = (
            _as_string_list(grain.get("entities"))
            if isinstance(grain, dict)
            else []
        )
        if layer == "DWS" or grain_entities:
            if grain_entities:
                missing_entities = [
                    entity
                    for entity in grain_entities
                    if entity not in defined_entities
                ]
                record(
                    table_name,
                    "METADATA_GRAIN_ENTITIES_DEFINED",
                    not missing_entities,
                    "grain.entities引用已定义实体",
                    (
                        "全部已定义"
                        if not missing_entities
                        else f"未定义实体: {missing_entities}"
                    ),
                    {
                        "grain_entities": grain_entities,
                        "defined_entities": sorted(defined_entities),
                    },
                    "",
                    f"grain.entities未定义={missing_entities}",
                )
            else:
                record(
                    table_name,
                    "METADATA_GRAIN_ENTITIES_PRESENT",
                    False,
                    "DWS模型配置grain.entities",
                    "未配置",
                    {"layer": layer},
                    "missing",
                    "缺少grain.entities",
                )

        if business_domain_config:
            if _data_domain_applies(layer):
                raw_domain = metadata.get("data_domain")
                normalized_domain = business_domain_config.normalize_domain(
                    raw_domain
                )
                if raw_domain in (None, ""):
                    ok = False
                    reason = "missing"
                    message = "data_domain未配置"
                elif not business_domain_config.is_valid_domain(
                    normalized_domain
                ):
                    ok = False
                    reason = "not_in_dictionary"
                    message = f"data_domain不在字典中: {raw_domain}"
                elif not _type_def_valid(
                    nc,
                    "DATA_DOMAIN_ID",
                    normalized_domain,
                ):
                    ok = False
                    reason = "type_mismatch"
                    message = f"data_domain不符合类型定义: {raw_domain}"
                else:
                    ok = True
                    reason = ""
                    message = ""
                record(
                    table_name,
                    "METADATA_DATA_DOMAIN_VALID",
                    ok,
                    "data_domain存在且符合业务字典",
                    normalized_domain if ok else str(raw_domain or "未配置"),
                    {
                        "raw_value": raw_domain,
                        "normalized_value": normalized_domain,
                    },
                    reason,
                    message,
                    SEVERITY_LOW if reason == "missing" else None,
                )

            if _business_area_applies(layer):
                raw_area = metadata.get("business_area")
                normalized_area = (
                    business_domain_config.normalize_business_area(raw_area)
                )
                if raw_area in (None, ""):
                    ok = False
                    reason = "missing"
                    message = "business_area未配置"
                elif not business_domain_config.is_valid_business_area(
                    normalized_area
                ):
                    ok = False
                    reason = "not_in_dictionary"
                    message = f"business_area不在字典中: {raw_area}"
                elif not _type_def_valid(
                    nc,
                    "BUSINESS_AREA_CODE",
                    normalized_area,
                ):
                    ok = False
                    reason = "type_mismatch"
                    message = f"business_area不符合类型定义: {raw_area}"
                else:
                    ok = True
                    reason = ""
                    message = ""
                record(
                    table_name,
                    "METADATA_BUSINESS_AREA_VALID",
                    ok,
                    "business_area存在且符合业务字典",
                    normalized_area if ok else str(raw_area or "未配置"),
                    {
                        "raw_value": raw_area,
                        "normalized_value": normalized_area,
                    },
                    reason,
                    message,
                    SEVERITY_LOW if reason == "missing" else None,
                )

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return finalize_dimension(
        dimension="metadata_health",
        score=round(passed / total * 100, 1) if total else 100.0,
        checks=checks,
        rules=METADATA_HEALTH_RULES,
    )
