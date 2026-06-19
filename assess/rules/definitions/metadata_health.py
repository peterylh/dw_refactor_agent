"""Model metadata health rule definitions."""

from __future__ import annotations

from assess.project_facts.business_metadata import (
    _business_area_applies,
    _data_domain_applies,
)
from assess.project_facts.entity_metadata import (
    grain_key_columns,
    primary_entity_codes,
)
from assess.result_model import make_check
from assess.rules.engine.base import AssessRule
from assess.scoring.config import SEVERITY_LOW
from assess.scoring.utils import _as_string_list, _type_def_valid


class _MetadataHealthRule(AssessRule):
    dimension = "metadata_health"
    domain = "table"
    target = "table"

    def check(
        self,
        table_name: str,
        ok: bool,
        expected: str,
        actual: str,
        evidence: dict | None = None,
        reason: str = "",
        message: str = "",
        severity: str | None = None,
    ) -> dict:
        issue = {}
        if reason:
            issue["message"] = message
        if severity:
            issue["severity"] = severity
        return make_check(
            rule_id=self.rule_id,
            target_type="table",
            target=table_name,
            passed=ok,
            expected=expected,
            actual=actual,
            evidence=evidence,
            message=message,
            issue=issue or None,
        )


class MetadataDimHasPrimaryEntityRule(_MetadataHealthRule):
    rule_id = "METADATA_DIM_HAS_PRIMARY_ENTITY"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DIM":
            return None
        return self.check(
            target["table_name"],
            bool(target["entity_codes"]),
            "DIM模型配置主实体编码",
            target["entity_codes"][0] if target["entity_codes"] else "未配置",
            {"layer": target["layer"]},
            "missing",
            "缺少entities.primary.code",
        )


class MetadataDimSemanticSubjectMatchesPrimaryRule(_MetadataHealthRule):
    rule_id = "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DIM":
            return None
        metadata = target["metadata"]
        semantic_subject = str(metadata.get("semantic_subject") or "").strip()
        primary_code = target["primary_code"]
        return self.check(
            target["table_name"],
            bool(
                semantic_subject
                and primary_code
                and semantic_subject == primary_code
            ),
            "semantic_subject等于DIM主实体编码",
            semantic_subject or "未配置",
            {
                "layer": target["layer"],
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


class MetadataEntityKeysExistRule(_MetadataHealthRule):
    rule_id = "METADATA_ENTITY_KEYS_EXIST"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        if not target["table"]:
            return []
        checks = []
        columns = target["columns"]
        entities = (
            [target["entity"]] if "entity" in target else target["entities"]
        )
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_code = str(entity.get("code") or "").strip()
            key_columns = _as_string_list(entity.get("key_columns"))
            if not key_columns:
                continue
            missing_keys = [key for key in key_columns if key not in columns]
            checks.append(
                self.check(
                    target["table_name"],
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
            )
        return checks


class MetadataRelationshipFromPrimaryRule(_MetadataHealthRule):
    rule_id = "METADATA_RELATIONSHIP_FROM_PRIMARY"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        if not target["table"] or not target["primary_code"]:
            return []
        checks = []
        primary_code = target["primary_code"]
        entities = (
            [target["entity"]] if "entity" in target else target["entities"]
        )
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_type = str(entity.get("type") or "").strip().lower()
            if entity_type == "primary":
                continue
            relationship = entity.get("relationship")
            if not isinstance(relationship, dict):
                continue
            entity_code = str(entity.get("code") or "").strip()
            from_entity = str(relationship.get("from_entity") or "").strip()
            checks.append(
                self.check(
                    target["table_name"],
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
            )
        return checks


class MetadataEntityNotDuplicatePrimaryRule(_MetadataHealthRule):
    rule_id = "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY"

    def evaluate(self, target: dict, rule_context: dict) -> list[dict]:
        if not target["table"] or not target["primary_code"]:
            return []
        checks = []
        primary_code = target["primary_code"]
        entities = (
            [target["entity"]] if "entity" in target else target["entities"]
        )
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_type = str(entity.get("type") or "").strip().lower()
            if entity_type == "primary":
                continue
            entity_code = str(entity.get("code") or "").strip()
            if not entity_code:
                continue
            checks.append(
                self.check(
                    target["table_name"],
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
            )
        return checks


class MetadataGrainKeysExistRule(_MetadataHealthRule):
    rule_id = "METADATA_GRAIN_KEYS_EXIST"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if not target["table"] or not isinstance(target["grain"], dict):
            return None
        grain_keys = grain_key_columns(target["metadata"])
        if not grain_keys:
            return None
        missing_grain_keys = [
            key for key in grain_keys if key not in target["columns"]
        ]
        return self.check(
            target["table_name"],
            not missing_grain_keys,
            "grain.keys存在于表字段",
            (
                "全部存在"
                if not missing_grain_keys
                else f"缺失字段: {missing_grain_keys}"
            ),
            {
                "grain_keys": grain_keys,
                "table_columns": sorted(target["columns"]),
            },
            "",
            f"grain.keys不存在={missing_grain_keys}",
        )


class MetadataGrainEntitiesPresentRule(_MetadataHealthRule):
    rule_id = "METADATA_GRAIN_ENTITIES_PRESENT"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if target["layer"] != "DWS" or target["grain_entities"]:
            return None
        return self.check(
            target["table_name"],
            False,
            "DWS模型配置grain.entities",
            "未配置",
            {"layer": target["layer"]},
            "missing",
            "缺少grain.entities",
        )


class MetadataGrainEntitiesDefinedRule(_MetadataHealthRule):
    rule_id = "METADATA_GRAIN_ENTITIES_DEFINED"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        grain_entities = target["grain_entities"]
        if not grain_entities:
            return None
        table_entity_codes = sorted(
            {
                str(entity.get("code") or "").strip()
                for entity in target["entities"]
                if str(entity.get("code") or "").strip()
            }
        )
        missing_entities = [
            entity
            for entity in grain_entities
            if entity not in table_entity_codes
        ]
        return self.check(
            target["table_name"],
            not missing_entities,
            "grain.entities引用当前表entities.code",
            (
                "全部在当前表entities中"
                if not missing_entities
                else f"当前表未声明实体: {missing_entities}"
            ),
            {
                "grain_entities": grain_entities,
                "table_entities": table_entity_codes,
            },
            "",
            f"grain.entities不在当前表entities中={missing_entities}",
        )


class MetadataDataDomainValidRule(_MetadataHealthRule):
    rule_id = "METADATA_DATA_DOMAIN_VALID"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if not rule_context[
            "business_domain_config"
        ] or not _data_domain_applies(target["layer"]):
            return None
        metadata = target["metadata"]
        business_domain_config = rule_context["business_domain_config"]
        nc = rule_context["naming_config"]
        raw_domain = metadata.get("data_domain")
        normalized_domain = business_domain_config.normalize_domain(raw_domain)
        if raw_domain in (None, ""):
            ok = False
            reason = "missing"
            message = "data_domain未配置"
        elif not business_domain_config.is_valid_domain(normalized_domain):
            ok = False
            reason = "not_in_dictionary"
            message = f"data_domain不在字典中: {raw_domain}"
        elif not _type_def_valid(nc, "DATA_DOMAIN_ID", normalized_domain):
            ok = False
            reason = "type_mismatch"
            message = f"data_domain不符合类型定义: {raw_domain}"
        else:
            ok = True
            reason = ""
            message = ""
        return self.check(
            target["table_name"],
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


class MetadataBusinessAreaValidRule(_MetadataHealthRule):
    rule_id = "METADATA_BUSINESS_AREA_VALID"

    def evaluate(self, target: dict, rule_context: dict) -> dict | None:
        if not rule_context[
            "business_domain_config"
        ] or not _business_area_applies(target["layer"]):
            return None
        metadata = target["metadata"]
        business_domain_config = rule_context["business_domain_config"]
        nc = rule_context["naming_config"]
        raw_area = metadata.get("business_area")
        normalized_area = business_domain_config.normalize_business_area(
            raw_area
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
        elif not _type_def_valid(nc, "BUSINESS_AREA_CODE", normalized_area):
            ok = False
            reason = "type_mismatch"
            message = f"business_area不符合类型定义: {raw_area}"
        else:
            ok = True
            reason = ""
            message = ""
        return self.check(
            target["table_name"],
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


METADATA_HEALTH_RULE_CLASSES = [
    MetadataDimHasPrimaryEntityRule,
    MetadataDimSemanticSubjectMatchesPrimaryRule,
    MetadataEntityKeysExistRule,
    MetadataRelationshipFromPrimaryRule,
    MetadataEntityNotDuplicatePrimaryRule,
    MetadataGrainKeysExistRule,
    MetadataGrainEntitiesPresentRule,
    MetadataGrainEntitiesDefinedRule,
    MetadataDataDomainValidRule,
    MetadataBusinessAreaValidRule,
]

METADATA_HEALTH_RULE_CLASSES_BY_ID = {
    rule_class.rule_id: rule_class
    for rule_class in METADATA_HEALTH_RULE_CLASSES
}


def _model_entity_codes(metadata: dict | None) -> list[str]:
    return primary_entity_codes(metadata)


def _table_column_names(table: dict) -> set[str]:
    return {
        str(column.get("name") or "").strip()
        for column in table.get("columns", []) or []
        if str(column.get("name") or "").strip()
    }
