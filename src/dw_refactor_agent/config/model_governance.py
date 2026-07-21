"""Governed model schema, field registry, and section-aware accessors."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

MODEL_SCHEMA_V2 = 2
MODEL_SCHEMA_V3 = 3
MODEL_GOVERNANCE_SCHEMA_VERSION = 1

MODEL_SECTIONS = (
    "classification",
    "business_semantics",
    "entities",
    "grain",
    "metrics",
)
STRUCTURE_SECTIONS = MODEL_SECTIONS[:4]
SECTION_STATUSES = frozenset({"active", "not_applicable", "quarantined"})
SEMANTIC_LAYERS = frozenset({"ODS", "DIM", "DWD", "DWS", "ADS", "OTHER"})
TABLE_TYPES = frozenset({"dimension", "fact", "bridge", "other"})
DIMENSION_ROLES = frozenset({"BASE", "ADDT"})
DIMENSION_CONTENT_TYPES = frozenset({"INFO", "TAG", "TREE"})

GOVERNANCE_REASON_SECTIONS = {
    "inspection_unavailable": frozenset(MODEL_SECTIONS),
    "inspection_not_requested": frozenset(MODEL_SECTIONS),
    "structure_bundle_incomplete": frozenset(STRUCTURE_SECTIONS),
    "classification_untrusted": frozenset({"classification"}),
    "business_semantics_untrusted": frozenset({"business_semantics"}),
    "business_process_missing": frozenset({"business_semantics"}),
    "catalog_code_unconfirmed": frozenset({"business_semantics"}),
    "entities_incomplete": frozenset({"entities"}),
    "grain_incomplete": frozenset({"grain"}),
    "metrics_incomplete": frozenset({"metrics"}),
    "dependent_structure_unavailable": frozenset({"metrics"}),
    "upstream_section_unavailable": frozenset(MODEL_SECTIONS),
}
GOVERNANCE_REASON_CODES = frozenset(GOVERNANCE_REASON_SECTIONS)


class UnsupportedModelGovernanceError(ValueError):
    """Raised when model schema/governance cannot be interpreted safely."""


class UnavailableModelSectionUsageError(RuntimeError):
    """Raised when quarantined metadata is treated as an ordinary value."""


@dataclass(frozen=True)
class ModelFieldPathRule:
    """One registered formal model path family."""

    path: str
    category: str
    section: str | None
    sources: tuple[str, ...]
    validator: str


def _rule(
    path: str,
    category: str,
    *,
    section: str | None = None,
    sources: Iterable[str],
    validator: str,
) -> ModelFieldPathRule:
    return ModelFieldPathRule(
        path=path,
        category=category,
        section=section,
        sources=tuple(sources),
        validator=validator,
    )


MODEL_FIELD_PATH_REGISTRY = (
    _rule(
        "version",
        "identity",
        sources=("schema",),
        validator="model_schema_version",
    ),
    _rule(
        "name",
        "identity",
        sources=("asset_manifest",),
        validator="model_name",
    ),
    _rule(
        "description",
        "identity",
        sources=("ddl_comment", "project_config"),
        validator="text",
    ),
    _rule(
        "operational_layer",
        "operational",
        sources=("asset_manifest",),
        validator="layer",
    ),
    _rule(
        "execution.*",
        "operational",
        sources=("task_sql", "asset_manifest", "project_config"),
        validator="execution_contract",
    ),
    _rule(
        "source",
        "operational",
        sources=("asset_manifest",),
        validator="source_scalar_or_mapping",
    ),
    _rule(
        "source.*",
        "operational",
        sources=("asset_manifest",),
        validator="source_mapping",
    ),
    _rule(
        "source_mapping.*",
        "operational",
        sources=("asset_manifest",),
        validator="source_mapping",
    ),
    _rule(
        "sensitivity",
        "data_governance",
        sources=("human", "policy"),
        validator="sensitivity",
    ),
    _rule(
        "sensitivity_policy.*",
        "data_governance",
        sources=("human", "policy"),
        validator="sensitivity_policy",
    ),
    _rule(
        "column_sensitivity[*].*",
        "data_governance",
        sources=("human", "policy"),
        validator="column_sensitivity",
    ),
    _rule(
        "row_policy",
        "data_governance",
        sources=("human", "policy"),
        validator="row_policy_scalar_or_mapping",
    ),
    _rule(
        "row_policy.*",
        "data_governance",
        sources=("human", "policy"),
        validator="row_policy_mapping",
    ),
    _rule(
        "human_review.*",
        "review_provenance",
        sources=("human",),
        validator="review_provenance",
    ),
    _rule(
        "layer",
        "semantic",
        section="classification",
        sources=("inspection", "asset_manifest"),
        validator="layer",
    ),
    _rule(
        "table_type",
        "semantic",
        section="classification",
        sources=("inspection", "deterministic_contract"),
        validator="table_type",
    ),
    _rule(
        "dimension_role",
        "semantic",
        section="classification",
        sources=("inspection", "deterministic_contract"),
        validator="dimension_role",
    ),
    _rule(
        "dimension_content_type",
        "semantic",
        section="classification",
        sources=("inspection", "deterministic_contract"),
        validator="dimension_content_type",
    ),
    _rule(
        "dimension_policy.*",
        "semantic",
        section="classification",
        sources=("inspection", "deterministic_contract"),
        validator="dimension_policy",
    ),
    *(
        _rule(
            path,
            "semantic",
            section="business_semantics",
            sources=("inspection", "confirmed_catalog"),
            validator="business_semantics",
        )
        for path in (
            "data_domain",
            "business_area",
            "business_process",
            "business_process_mode",
            "business_processes[*]",
            "business_process_sources[*]",
            "semantic_subject",
        )
    ),
    _rule(
        "entities[*].*",
        "semantic",
        section="entities",
        sources=("inspection", "ddl", "lineage"),
        validator="entity",
    ),
    _rule(
        "hierarchy_roles[*].*",
        "semantic",
        section="entities",
        sources=("inspection", "ddl", "lineage"),
        validator="hierarchy_role",
    ),
    _rule(
        "entity.*",
        "legacy_semantic_alias",
        section="entities",
        sources=("v2_migration",),
        validator="legacy_entity",
    ),
    _rule(
        "related_entities[*].*",
        "legacy_semantic_alias",
        section="entities",
        sources=("v2_migration",),
        validator="legacy_entity",
    ),
    _rule(
        "grain.*",
        "semantic",
        section="grain",
        sources=("inspection", "ddl", "lineage"),
        validator="grain",
    ),
    _rule(
        "business_date.*",
        "semantic",
        section="grain",
        sources=("inspection", "ddl", "lineage"),
        validator="business_date",
    ),
    _rule(
        "degenerate_dimensions[*]",
        "semantic",
        section="grain",
        sources=("inspection", "ddl", "lineage"),
        validator="degenerate_dimension",
    ),
    _rule(
        "degenerate_dimensions[*].*",
        "semantic",
        section="grain",
        sources=("inspection", "ddl", "lineage"),
        validator="degenerate_dimension",
    ),
    *(
        _rule(
            path,
            "semantic",
            section="metrics",
            sources=("inspection", "ddl", "task_sql", "lineage"),
            validator="metric",
        )
        for path in (
            "atomic_metrics[*]",
            "atomic_metrics[*].*",
            "derived_metrics[*]",
            "derived_metrics[*].*",
            "calculated_metrics[*]",
            "calculated_metrics[*].*",
            "metric_semantics[*]",
            "metric_semantics[*].*",
            "application_rules[*]",
            "application_rules[*].*",
        )
    ),
    _rule(
        "metrics[*]",
        "legacy_semantic_alias",
        section="metrics",
        sources=("v2_migration",),
        validator="legacy_metric",
    ),
    _rule(
        "metrics[*].*",
        "legacy_semantic_alias",
        section="metrics",
        sources=("v2_migration",),
        validator="legacy_metric",
    ),
    _rule(
        "governance.*",
        "governance",
        sources=("decision_policy",),
        validator="governance",
    ),
)


def _root_for_pattern(pattern: str) -> str:
    return pattern.split(".", 1)[0].split("[", 1)[0]


REGISTERED_MODEL_ROOT_FIELDS = frozenset(
    _root_for_pattern(rule.path) for rule in MODEL_FIELD_PATH_REGISTRY
)


def model_field_rule(path: str) -> ModelFieldPathRule | None:
    """Return the exact registered rule family for one normalized path."""
    text = str(path or "").strip()
    for rule in MODEL_FIELD_PATH_REGISTRY:
        pattern = rule.path
        if text == pattern:
            return rule
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            if text == prefix or text.startswith(prefix + "."):
                return rule
        if pattern.endswith("[*]") and text == pattern:
            return rule
    return None


def iter_model_schema_paths(value: Any, prefix: str = "") -> tuple[str, ...]:
    """Return normalized scalar/empty-container paths for registry checks."""
    paths = []
    if isinstance(value, Mapping):
        if prefix and not value:
            paths.append(prefix)
        for key in sorted(value):
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(iter_model_schema_paths(value[key], child))
    elif isinstance(value, list):
        item_prefix = f"{prefix}[*]"
        if not value:
            paths.append(prefix)
        for item in value:
            paths.extend(iter_model_schema_paths(item, item_prefix))
    elif prefix:
        paths.append(prefix)
    return tuple(sorted(set(paths)))


def unregistered_model_paths(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    """Return model paths not covered by the formal registry."""
    unknown = {
        str(key)
        for key in metadata
        if str(key) not in REGISTERED_MODEL_ROOT_FIELDS
    }
    unknown.update(
        path
        for path in iter_model_schema_paths(metadata)
        if path not in REGISTERED_MODEL_ROOT_FIELDS
        and model_field_rule(path) is None
    )
    return tuple(sorted(unknown))


@dataclass(frozen=True)
class ModelGovernance:
    """Validated v3 quarantine metadata."""

    withheld_sections: tuple[str, ...] = ()
    reasons: tuple[tuple[str, tuple[str, ...]], ...] = ()
    schema_version: int = MODEL_GOVERNANCE_SCHEMA_VERSION
    status: str = "active"

    def reasons_for(self, section: str) -> tuple[str, ...]:
        return dict(self.reasons).get(section, ())


@dataclass(frozen=True)
class UnavailableModelSection:
    """Explicit result returned for a quarantined semantic section."""

    section: str
    reasons: tuple[str, ...]

    @property
    def status(self) -> str:
        return "quarantined"

    def __bool__(self) -> bool:
        raise UnavailableModelSectionUsageError(
            f"model section {self.section!r} is quarantined; "
            "inspect the section state explicitly"
        )


@dataclass(frozen=True)
class NotApplicableModelSection:
    """Explicit result returned when a semantic section does not apply."""

    section: str

    @property
    def status(self) -> str:
        return "not_applicable"

    def __bool__(self) -> bool:
        raise UnavailableModelSectionUsageError(
            f"model section {self.section!r} is not applicable; "
            "inspect the section state explicitly"
        )


class GovernedModelMetadata(dict):
    """Dict-compatible validated model view with governance state."""

    def __init__(
        self,
        metadata: Mapping[str, Any],
        *,
        governance: ModelGovernance,
        source: str,
    ):
        super().__init__(copy.deepcopy(dict(metadata)))
        self.governance = governance
        self.source = source

    @property
    def model_version(self) -> int:
        return int(self["version"])

    def section_status(self, section: str) -> str:
        return model_section_status(self, section)


def _error(source: str, message: str) -> UnsupportedModelGovernanceError:
    label = f"{source}: " if source else ""
    return UnsupportedModelGovernanceError(label + message)


def _strict_int(value: Any, *, source: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(source, f"{field} must be an integer")
    return value


def _validate_execution_contract(
    value: Any,
    *,
    source: str,
) -> None:
    if not isinstance(value, dict):
        raise _error(source, "v3 execution must be a mapping")
    mode = str(value.get("mode") or "task").strip().lower()
    if mode not in {"task", "taskless"}:
        raise _error(source, "v3 execution.mode must be task or taskless")
    if mode == "taskless":
        forbidden = sorted(
            field
            for field in (
                "materialized",
                "full_refresh_strategy",
                "slice",
                "historical_replay_supported",
            )
            if field in value
        )
        if forbidden:
            raise _error(
                source,
                "v3 taskless execution cannot define task fields: "
                + ", ".join(forbidden),
            )
        return
    materialized = str(value.get("materialized") or "").strip().lower()
    strategy = str(value.get("full_refresh_strategy") or "").strip().lower()
    if materialized not in {"incremental", "full"}:
        raise _error(
            source,
            "v3 execution.materialized must be incremental or full",
        )
    if strategy not in {
        "replay_slices",
        "companion",
        "legacy_full_refresh",
        "replace_all",
    }:
        raise _error(
            source,
            "v3 execution.full_refresh_strategy is missing or unsupported",
        )
    if materialized == "full":
        if strategy != "replace_all" or value.get("slice") not in (None, {}):
            raise _error(
                source,
                "v3 full execution requires replace_all and no slice",
            )
        return
    if strategy == "replace_all":
        raise _error(
            source,
            "v3 incremental execution cannot use replace_all",
        )
    raw_slice = value.get("slice")
    if not isinstance(raw_slice, dict):
        raise _error(source, "v3 incremental execution requires slice")
    if any(
        not str(raw_slice.get(field) or "").strip()
        for field in ("param", "column", "period")
    ):
        raise _error(
            source,
            "v3 execution.slice requires param, column, and period",
        )


def _validate_list_field(
    raw: Mapping[str, Any],
    field_name: str,
    *,
    source: str,
    item_types: tuple[type, ...],
) -> None:
    if field_name not in raw:
        return
    value = raw[field_name]
    if not isinstance(value, list) or any(
        not isinstance(item, item_types) for item in value
    ):
        raise _error(source, f"v3 {field_name} has an invalid list shape")


def _validate_v3_field_shapes(
    raw: Mapping[str, Any],
    *,
    source: str,
) -> None:
    layer = str(raw.get("layer") or "").strip().upper()
    if layer and layer not in SEMANTIC_LAYERS:
        raise _error(source, f"unsupported v3 semantic layer: {layer}")
    table_type = str(raw.get("table_type") or "").strip().lower()
    if table_type and table_type not in TABLE_TYPES:
        raise _error(source, f"unsupported v3 table_type: {table_type}")
    dimension_role = str(raw.get("dimension_role") or "").strip().upper()
    if dimension_role and dimension_role not in DIMENSION_ROLES:
        raise _error(
            source, f"unsupported v3 dimension_role: {dimension_role}"
        )
    content_type = str(raw.get("dimension_content_type") or "").strip().upper()
    if content_type and content_type not in DIMENSION_CONTENT_TYPES:
        raise _error(
            source,
            "unsupported v3 dimension_content_type: " + content_type,
        )

    for field_name in (
        "description",
        "data_domain",
        "business_area",
        "business_process",
        "business_process_mode",
        "semantic_subject",
        "sensitivity",
    ):
        if field_name in raw and not isinstance(raw[field_name], str):
            raise _error(source, f"v3 {field_name} must be a string")
    for field_name in (
        "source_mapping",
        "sensitivity_policy",
        "human_review",
        "dimension_policy",
        "grain",
        "business_date",
    ):
        if field_name in raw and not isinstance(raw[field_name], dict):
            raise _error(source, f"v3 {field_name} must be a mapping")
    for field_name in ("source", "row_policy"):
        if field_name in raw and not isinstance(raw[field_name], (str, dict)):
            raise _error(
                source,
                f"v3 {field_name} must be a string or mapping",
            )
    for field_name in (
        "column_sensitivity",
        "entities",
        "hierarchy_roles",
        "metric_semantics",
        "application_rules",
    ):
        _validate_list_field(
            raw,
            field_name,
            source=source,
            item_types=(dict,),
        )
    for field_name in (
        "atomic_metrics",
        "derived_metrics",
        "calculated_metrics",
        "degenerate_dimensions",
    ):
        _validate_list_field(
            raw,
            field_name,
            source=source,
            item_types=(str, dict),
        )
    _validate_list_field(
        raw,
        "business_processes",
        source=source,
        item_types=(str,),
    )
    _validate_list_field(
        raw,
        "business_process_sources",
        source=source,
        item_types=(str,),
    )


def _validate_governance(
    raw: Any,
    *,
    source: str,
) -> ModelGovernance:
    if not isinstance(raw, dict):
        raise _error(source, "v3 governance must be a mapping")
    expected_fields = {
        "status",
        "schema_version",
        "withheld_sections",
        "reasons",
    }
    if set(raw) != expected_fields:
        raise _error(source, "v3 governance fields are incomplete or unknown")
    schema_version = _strict_int(
        raw.get("schema_version"),
        source=source,
        field="governance.schema_version",
    )
    if schema_version != MODEL_GOVERNANCE_SCHEMA_VERSION:
        raise _error(source, "unsupported governance schema version")
    if raw.get("status") != "quarantined":
        raise _error(source, "unsupported governance status")

    withheld = raw.get("withheld_sections")
    reasons = raw.get("reasons")
    if not isinstance(withheld, list) or not isinstance(reasons, dict):
        raise _error(source, "invalid governance sections or reasons")
    if any(not isinstance(section, str) for section in withheld):
        raise _error(source, "governance sections must be strings")
    unknown_sections = set(withheld) - set(MODEL_SECTIONS)
    if unknown_sections:
        raise _error(
            source,
            "unknown governance section: "
            + ", ".join(sorted(unknown_sections)),
        )
    canonical_withheld = [
        section for section in MODEL_SECTIONS if section in set(withheld)
    ]
    if not canonical_withheld or withheld != canonical_withheld:
        raise _error(
            source,
            "withheld_sections must be non-empty, unique, and stable",
        )
    if set(reasons) != set(withheld):
        raise _error(
            source,
            "governance reasons must exactly match withheld_sections",
        )

    normalized_reasons = []
    for section in canonical_withheld:
        section_reasons = reasons.get(section)
        if (
            not isinstance(section_reasons, list)
            or not section_reasons
            or any(not isinstance(reason, str) for reason in section_reasons)
            or section_reasons != sorted(set(section_reasons))
        ):
            raise _error(
                source,
                f"governance reasons for {section} must be sorted and unique",
            )
        for reason in section_reasons:
            allowed_sections = GOVERNANCE_REASON_SECTIONS.get(reason)
            if allowed_sections is None or section not in allowed_sections:
                raise _error(
                    source,
                    f"unknown governance reason {reason!r} for {section}",
                )
        normalized_reasons.append((section, tuple(section_reasons)))

    return ModelGovernance(
        status="quarantined",
        schema_version=schema_version,
        withheld_sections=tuple(canonical_withheld),
        reasons=tuple(normalized_reasons),
    )


def _top_level_sections() -> dict[str, str]:
    sections = {}
    for rule in MODEL_FIELD_PATH_REGISTRY:
        if rule.section is None:
            continue
        root = _root_for_pattern(rule.path)
        existing = sections.setdefault(root, rule.section)
        if existing != rule.section:
            raise RuntimeError(f"conflicting model registry section: {root}")
    return sections


MODEL_FIELD_SECTIONS = _top_level_sections()
MODEL_SECTION_FIELDS = {
    section: tuple(
        dict.fromkeys(
            _root_for_pattern(rule.path)
            for rule in MODEL_FIELD_PATH_REGISTRY
            if rule.section == section and rule.category == "semantic"
        )
    )
    for section in MODEL_SECTIONS
}
MODEL_SECTION_LEGACY_ALIAS_FIELDS = {
    section: tuple(
        dict.fromkeys(
            _root_for_pattern(rule.path)
            for rule in MODEL_FIELD_PATH_REGISTRY
            if rule.section == section
            and rule.category == "legacy_semantic_alias"
        )
    )
    for section in MODEL_SECTIONS
}
V3_LEGACY_ALIAS_FIELDS = frozenset(
    {
        _root_for_pattern(rule.path)
        for rule in MODEL_FIELD_PATH_REGISTRY
        if rule.category == "legacy_semantic_alias"
    }
)


def validate_model_metadata(
    metadata: Mapping[str, Any],
    *,
    source: str = "",
) -> GovernedModelMetadata:
    """Validate one v2/v3 model and return its governed default view."""
    if not isinstance(metadata, Mapping):
        raise _error(source, "model metadata must be a mapping")
    raw = copy.deepcopy(dict(metadata))
    unknown_paths = unregistered_model_paths(raw)
    if unknown_paths:
        raise _error(
            source,
            "unregistered model schema paths: " + ", ".join(unknown_paths),
        )
    version = _strict_int(raw.get("version"), source=source, field="version")
    if version not in {MODEL_SCHEMA_V2, MODEL_SCHEMA_V3}:
        raise _error(source, f"unsupported model version: {version}")
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        raise _error(source, "model name is required")

    if version == MODEL_SCHEMA_V2:
        if "governance" in raw or "operational_layer" in raw:
            raise _error(
                source,
                "v2 models cannot define governance or operational_layer",
            )
        return GovernedModelMetadata(
            raw,
            governance=ModelGovernance(),
            source=source,
        )

    aliases = sorted(V3_LEGACY_ALIAS_FIELDS.intersection(raw))
    if aliases:
        raise _error(
            source,
            "v3 models cannot contain legacy aliases: " + ", ".join(aliases),
        )
    operational_layer = str(raw.get("operational_layer") or "").upper()
    if operational_layer not in {"ODS", "DIM", "DWD", "DWS", "ADS"}:
        raise _error(source, "v3 operational_layer is missing or invalid")
    _validate_execution_contract(raw.get("execution"), source=source)
    _validate_v3_field_shapes(raw, source=source)

    governance = (
        _validate_governance(raw["governance"], source=source)
        if "governance" in raw
        else ModelGovernance()
    )
    withheld = set(governance.withheld_sections)
    classification_withheld = "classification" in withheld
    structure_withheld = withheld.intersection(STRUCTURE_SECTIONS)
    if (
        operational_layer in {"DIM", "DWD", "DWS"}
        and structure_withheld
        and structure_withheld != set(STRUCTURE_SECTIONS)
    ):
        raise _error(
            source,
            "MID structure-semantics sections must be withheld as one bundle",
        )
    if (
        operational_layer in {"DIM", "DWD", "DWS"}
        and structure_withheld
        and "metrics" not in withheld
    ):
        raise _error(
            source,
            "withheld MID structure requires metrics quarantine",
        )
    if not classification_withheld and (
        not str(raw.get("layer") or "").strip()
        or not str(raw.get("table_type") or "").strip()
    ):
        raise _error(
            source,
            "active v3 classification requires layer and table_type",
        )
    if (
        "metrics" in withheld
        and not classification_withheld
        and operational_layer not in {"ODS", "ADS"}
        and not (
            str(raw.get("layer") or "").upper() in {"DWD", "DWS"}
            and str(raw.get("table_type") or "").lower() == "fact"
        )
    ):
        raise _error(
            source,
            "not-applicable metrics cannot be withheld",
        )
    semantic_layer = str(raw.get("layer") or "").upper()
    table_type = str(raw.get("table_type") or "").lower()
    metric_fields = MODEL_SECTION_FIELDS["metrics"]
    metrics_applicable = operational_layer in {"ODS", "ADS"} and any(
        field in raw for field in metric_fields
    )
    metrics_applicable = metrics_applicable or (
        semantic_layer in {"DWD", "DWS"} and table_type == "fact"
    )
    if (
        not classification_withheld
        and not metrics_applicable
        and any(field in raw for field in metric_fields)
    ):
        raise _error(
            source,
            "not-applicable metrics section retains formal fields",
        )
    for field_name, section in MODEL_FIELD_SECTIONS.items():
        if section in withheld and field_name in raw:
            raise _error(
                source,
                f"withheld section {section} retains field {field_name}",
            )
    return GovernedModelMetadata(
        raw,
        governance=governance,
        source=source,
    )


def ensure_governed_model(
    metadata: Mapping[str, Any],
    *,
    source: str = "",
) -> GovernedModelMetadata:
    if isinstance(metadata, GovernedModelMetadata):
        return validate_model_metadata(
            metadata,
            source=source or metadata.source,
        )
    return validate_model_metadata(metadata, source=source)


def model_section_status(
    metadata: Mapping[str, Any],
    section: str,
) -> str:
    """Return active/not_applicable/quarantined for a semantic section."""
    model = ensure_governed_model(metadata)
    if section not in MODEL_SECTIONS:
        raise UnsupportedModelGovernanceError(
            f"unknown model section: {section!r}"
        )
    if section in model.governance.withheld_sections:
        return "quarantined"
    if section == "classification":
        return "active"

    section_fields = MODEL_SECTION_FIELDS[section]
    if model.model_version == MODEL_SCHEMA_V2:
        section_fields += MODEL_SECTION_LEGACY_ALIAS_FIELDS[section]
    operational_layer = (
        str(
            model.get(
                "operational_layer"
                if model.model_version == MODEL_SCHEMA_V3
                else "layer"
            )
            or ""
        )
        .strip()
        .upper()
    )
    if section == "metrics":
        if model.model_version == MODEL_SCHEMA_V2 and any(
            field in model for field in section_fields
        ):
            return "active"
        semantic_layer = str(model.get("layer") or "").upper()
        table_type = str(model.get("table_type") or "").lower()
        if semantic_layer in {"DWD", "DWS"} and table_type == "fact":
            return "active"
        if operational_layer in {"ODS", "ADS"} and any(
            field in model for field in section_fields
        ):
            return "active"
        return "not_applicable"
    if operational_layer in {"ODS", "ADS"}:
        return (
            "active"
            if any(field in model for field in section_fields)
            else "not_applicable"
        )
    return "active"


def _section_value(
    metadata: Mapping[str, Any],
    section: str,
    value: Any,
) -> Any:
    model = ensure_governed_model(metadata)
    status = model_section_status(model, section)
    if status == "quarantined":
        return UnavailableModelSection(
            section=section,
            reasons=model.governance.reasons_for(section),
        )
    if status == "not_applicable":
        return NotApplicableModelSection(section=section)
    return copy.deepcopy(value)


def get_operational_layer(metadata: Mapping[str, Any]) -> str | None:
    model = ensure_governed_model(metadata)
    field_name = (
        "operational_layer"
        if model.model_version == MODEL_SCHEMA_V3
        else "layer"
    )
    value = str(model.get(field_name) or "").strip()
    return value.upper() if value else None


def get_execution_contract(metadata: Mapping[str, Any]) -> dict[str, Any]:
    model = ensure_governed_model(metadata)
    value = model.get("execution")
    if value is None and model.model_version == MODEL_SCHEMA_V2:
        return {}
    if not isinstance(value, dict):
        raise UnsupportedModelGovernanceError(
            f"{model.source + ': ' if model.source else ''}"
            "execution must be a mapping"
        )
    return copy.deepcopy(value)


def get_semantic_layer(
    metadata: Mapping[str, Any],
) -> str | UnavailableModelSection | None:
    model = ensure_governed_model(metadata)
    value = str(model.get("layer") or "").strip()
    return _section_value(
        model,
        "classification",
        value.upper() if value else None,
    )


def get_table_type(
    metadata: Mapping[str, Any],
) -> str | UnavailableModelSection | None:
    model = ensure_governed_model(metadata)
    value = str(model.get("table_type") or "").strip().lower()
    return _section_value(
        model,
        "classification",
        value or None,
    )


def _canonical_section_payload(
    model: GovernedModelMetadata,
    section: str,
) -> dict[str, Any]:
    value = {
        field: copy.deepcopy(model[field])
        for field in MODEL_SECTION_FIELDS[section]
        if field in model
    }
    if section == "classification":
        if "layer" in value:
            value["layer"] = str(value["layer"]).strip().upper()
        if "table_type" in value:
            value["table_type"] = str(value["table_type"]).strip().lower()
    if (
        section == "entities"
        and model.model_version == MODEL_SCHEMA_V2
        and any(
            field in model
            for field in ("entities", "entity", "related_entities")
        )
    ):
        value["entities"] = _v2_entities(model)
    if section == "metrics":
        for field in MODEL_SECTION_FIELDS["metrics"]:
            value.setdefault(field, [])
        if model.model_version == MODEL_SCHEMA_V2 and not any(
            value[field] for field in MODEL_SECTION_FIELDS["metrics"]
        ):
            legacy = model.get("metrics")
            if isinstance(legacy, list):
                value["atomic_metrics"] = [
                    {"name": str(item)}
                    if not isinstance(item, dict)
                    else dict(item)
                    for item in legacy
                ]
    return value


def get_semantic_section(
    metadata: Mapping[str, Any],
    section: str,
) -> dict[str, Any] | UnavailableModelSection | NotApplicableModelSection:
    """Return a complete canonical payload for one semantic section."""
    model = ensure_governed_model(metadata)
    if section not in MODEL_SECTIONS:
        raise UnsupportedModelGovernanceError(
            f"unknown model section: {section!r}"
        )
    return _section_value(
        model,
        section,
        _canonical_section_payload(model, section),
    )


def get_classification(
    metadata: Mapping[str, Any],
) -> dict[str, Any] | UnavailableModelSection:
    """Return the complete classification section."""
    return get_semantic_section(metadata, "classification")


def get_metrics(
    metadata: Mapping[str, Any],
) -> (
    dict[str, list[Any]] | UnavailableModelSection | NotApplicableModelSection
):
    return get_semantic_section(metadata, "metrics")


def _v2_entities(model: Mapping[str, Any]) -> list[dict[str, Any]]:
    entities = model.get("entities")
    if isinstance(entities, list):
        return [dict(item) for item in entities if isinstance(item, dict)]
    normalized = []
    primary = model.get("entity")
    if isinstance(primary, dict):
        item = dict(primary)
        item.setdefault("type", "primary")
        normalized.append(item)
    related = model.get("related_entities")
    if isinstance(related, list):
        for raw in related:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item.setdefault("type", "foreign")
            normalized.append(item)
    return normalized


def get_entities(
    metadata: Mapping[str, Any],
) -> (
    list[dict[str, Any]] | UnavailableModelSection | NotApplicableModelSection
):
    model = ensure_governed_model(metadata)
    section = get_semantic_section(model, "entities")
    if isinstance(
        section,
        (UnavailableModelSection, NotApplicableModelSection),
    ):
        return section
    return [
        dict(item)
        for item in section.get("entities", [])
        if isinstance(item, dict)
    ]


def get_grain(
    metadata: Mapping[str, Any],
) -> dict[str, Any] | UnavailableModelSection | NotApplicableModelSection:
    model = ensure_governed_model(metadata)
    section = get_semantic_section(model, "grain")
    if isinstance(
        section,
        (UnavailableModelSection, NotApplicableModelSection),
    ):
        return section
    grain = section.get("grain")
    return dict(grain) if isinstance(grain, dict) else {}


def get_business_semantics(
    metadata: Mapping[str, Any],
) -> dict[str, Any] | UnavailableModelSection | NotApplicableModelSection:
    return get_semantic_section(metadata, "business_semantics")
