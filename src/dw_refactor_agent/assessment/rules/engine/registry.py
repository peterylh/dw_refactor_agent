"""Rule domain/target registry for assess scorers."""

from __future__ import annotations

from dataclasses import dataclass

from dw_refactor_agent.assessment.rules.engine.base import AssessRule


@dataclass(frozen=True)
class RuleSpec:
    """Execution grouping metadata for an assessment rule."""

    rule_id: str
    dimension: str
    domain: str
    target: str


def _rule_classes() -> list[type[AssessRule]]:
    from dw_refactor_agent.assessment.rules.definitions.asset_completeness import (
        ASSET_COMPLETENESS_RULE_CLASSES,
    )
    from dw_refactor_agent.assessment.rules.definitions.depth import (
        DepthMiddleLayerIsOptimalRule,
    )
    from dw_refactor_agent.assessment.rules.definitions.metadata_health import (
        METADATA_HEALTH_RULE_CLASSES,
    )
    from dw_refactor_agent.assessment.rules.definitions.model_design import (
        MODEL_DESIGN_RULE_CLASSES,
    )
    from dw_refactor_agent.assessment.rules.definitions.naming import (
        NAMING_RULE_CLASSES,
    )
    from dw_refactor_agent.assessment.rules.definitions.reuse import (
        ReuseDownstreamReachesTargetRule,
    )
    from dw_refactor_agent.assessment.rules.definitions.task_sql_quality import (
        CODE_QUALITY_RULE_CLASSES,
    )

    return [
        ReuseDownstreamReachesTargetRule,
        DepthMiddleLayerIsOptimalRule,
        *MODEL_DESIGN_RULE_CLASSES,
        *NAMING_RULE_CLASSES,
        *ASSET_COMPLETENESS_RULE_CLASSES,
        *METADATA_HEALTH_RULE_CLASSES,
        *CODE_QUALITY_RULE_CLASSES,
    ]


def rule_classes_by_id() -> dict[str, type[AssessRule]]:
    classes = {}
    for rule_class in _rule_classes():
        if rule_class.rule_id in classes:
            raise ValueError(f"重复评估规则: {rule_class.rule_id}")
        classes[rule_class.rule_id] = rule_class
    return classes


def rule_specs_by_id() -> dict[str, RuleSpec]:
    return {
        rule_id: RuleSpec(
            rule_id=rule_id,
            dimension=rule_class.dimension,
            domain=rule_class.domain,
            target=rule_class.target,
        )
        for rule_id, rule_class in rule_classes_by_id().items()
    }
