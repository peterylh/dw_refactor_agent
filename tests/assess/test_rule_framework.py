from dw_refactor_agent.assessment.assessment_context import AssessmentContext
from dw_refactor_agent.assessment.project_facts.asset_catalog import (
    build_asset_catalog,
)
from dw_refactor_agent.assessment.rules import (
    RuleRunner,
    RuleSelection,
)
from dw_refactor_agent.assessment.rules.definitions.task_sql_quality import (
    CODE_RULE_NO_SELECT_STAR,
)
from dw_refactor_agent.assessment.rules.dimensions.task_sql_quality import (
    score_code_quality,
)
from dw_refactor_agent.assessment.rules.engine.base import AssessRule


def _catalog_for_task(tmp_path, task_name, sql):
    project_dir = tmp_path / "demo"
    (project_dir / "tasks").mkdir(parents=True)
    (project_dir / "tasks" / task_name).write_text(sql, encoding="utf-8")
    catalog = build_asset_catalog(
        [],
        None,
        project_dir,
        edges=[],
        indirect_edges=[],
    )
    return AssessmentContext.from_facts(assets=catalog)


def test_rule_runner_executes_enabled_rules_for_each_target():
    class FirstRule(AssessRule):
        rule_id = "FIRST"
        dimension = "demo"
        domain = "table"
        target = "table"

        def evaluate(self, target, rule_context):
            return {
                "rule_id": self.rule_id,
                "target": target["name"] + rule_context["suffix"],
            }

    class SecondRule(AssessRule):
        rule_id = "SECOND"
        dimension = "demo"
        domain = "table"
        target = "table"

        def evaluate(self, target, rule_context):
            return [
                {
                    "rule_id": self.rule_id,
                    "target": target["name"] + rule_context["suffix"],
                }
            ]

    runner = RuleRunner(
        RuleSelection(disabled={"SECOND"}),
        rule_classes={
            FirstRule.rule_id: FirstRule,
            SecondRule.rule_id: SecondRule,
        },
    )

    checks = runner.run(
        "table",
        "table",
        targets=[{"name": "a"}, {"name": "b"}],
        rule_context={"suffix": "!"},
    )

    assert checks == [
        {"rule_id": "FIRST", "target": "a!"},
        {"rule_id": "FIRST", "target": "b!"},
    ]


def test_score_code_quality_can_disable_individual_rule(tmp_path):
    context = _catalog_for_task(
        tmp_path,
        "dws_sales.sql",
        """
INSERT INTO demo.dws_sales
SELECT *
FROM demo.dwd_sales;
""",
    )

    result = score_code_quality(
        context,
        rule_selection=RuleSelection(disabled={CODE_RULE_NO_SELECT_STAR}),
    )

    assert result["score"] == 100.0
    assert result["rule_summary"] == {}
    assert result["checks"] == []
    assert result["issues"] == []
