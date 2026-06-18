from assess.assessment_context import AssessmentContext
from assess.project_facts.asset_catalog import build_asset_catalog
from assess.rules import RuleRunner, RuleSelection, rule_specs_by_id
from assess.rules.definitions.task_sql_quality import CODE_RULE_NO_SELECT_STAR
from assess.rules.dimensions.task_sql_quality import (
    score_code_quality,
)
from assess.rules.engine.base import AssessRule
from assess.rules.engine.registry import rule_classes_by_id


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


def test_rule_specs_use_domain_and_target_for_current_rules():
    specs = rule_specs_by_id()

    assert specs["REUSE_DOWNSTREAM_REACHES_TARGET"].domain == "table"
    assert specs["REUSE_DOWNSTREAM_REACHES_TARGET"].target == "table"
    assert specs["ARCH_SKIP_LAYER_DEPENDENCY"].domain == "dependency"
    assert specs["ARCH_SKIP_LAYER_DEPENDENCY"].target == "edge"
    assert specs["ASSET_TASK_SINGLE_OUTPUT"].domain == "asset"
    assert specs["ASSET_TASK_SINGLE_OUTPUT"].target == "task"
    assert specs["NAMING_TASK_OUTPUT_NAME"].domain == "asset"
    assert specs["NAMING_TASK_OUTPUT_NAME"].target == "file"
    assert specs["CODE_NO_SELECT_STAR_IN_WRITE"].domain == "task"
    assert specs["CODE_NO_SELECT_STAR_IN_WRITE"].target == "sql"


def test_rule_runner_groups_enabled_rules_by_domain_and_target():
    runner = RuleRunner(
        RuleSelection(
            only={
                "ASSET_TASK_SINGLE_OUTPUT",
                "ASSET_TASK_LINEAGE_MATCHES_OUTPUT",
                "CODE_NO_SELECT_STAR_IN_WRITE",
            }
        )
    )

    assert runner.rule_ids_for("asset", "task") == [
        "ASSET_TASK_SINGLE_OUTPUT",
        "ASSET_TASK_LINEAGE_MATCHES_OUTPUT",
    ]
    assert runner.rule_ids_for("task", "sql") == [
        "CODE_NO_SELECT_STAR_IN_WRITE"
    ]
    assert runner.is_enabled("NAMING_TABLE_TEMPLATE") is False


def test_rule_runner_executes_enabled_rules_for_each_target():
    class FirstRule(AssessRule):
        rule_id = "FIRST"
        dimension = "demo"
        domain = "table"
        target = "table"

        def evaluate(self, target, facts):
            return {"rule_id": self.rule_id, "target": target["name"]}

    class SecondRule(AssessRule):
        rule_id = "SECOND"
        dimension = "demo"
        domain = "table"
        target = "table"

        def evaluate(self, target, facts):
            return [{"rule_id": self.rule_id, "target": target["name"]}]

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
        facts={},
    )

    assert checks == [
        {"rule_id": "FIRST", "target": "a"},
        {"rule_id": "FIRST", "target": "b"},
    ]


def test_each_registered_rule_has_an_independent_class():
    specs = rule_specs_by_id()
    classes = rule_classes_by_id()

    assert set(classes) == set(specs)
    assert len({rule_class for rule_class in classes.values()}) == len(specs)

    for rule_id, rule_class in classes.items():
        spec = specs[rule_id]
        assert issubclass(rule_class, AssessRule)
        assert rule_class is not AssessRule
        assert rule_class.rule_id == rule_id
        assert rule_class.dimension == spec.dimension
        assert rule_class.domain == spec.domain
        assert rule_class.target == spec.target


def test_allowed_dependency_is_not_a_registered_rule():
    specs = rule_specs_by_id()
    classes = rule_classes_by_id()

    assert "ARCH_ALLOWED_DEPENDENCY" not in specs
    assert "ARCH_ALLOWED_DEPENDENCY" not in classes


def test_each_registered_rule_owns_an_evaluate_method():
    classes = rule_classes_by_id()

    for rule_id, rule_class in classes.items():
        assert "evaluate" in rule_class.__dict__, rule_id


def test_rule_logic_and_dimension_execution_are_separate():
    from pathlib import Path

    rules_dir = Path(__file__).resolve().parents[2] / "assess" / "rules"
    for path in (rules_dir / "definitions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "finalize_dimension(" not in source

    for path in (rules_dir / "dimensions").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "make_check(" not in source


def test_rule_package_has_separate_engine_definitions_and_dimensions():
    from pathlib import Path

    rules_dir = Path(__file__).resolve().parents[2] / "assess" / "rules"
    expected_engine = {
        "base.py",
        "filtering.py",
        "registry.py",
        "runner.py",
        "selection.py",
    }
    expected_rule_modules = {
        "asset_completeness.py",
        "depth.py",
        "metadata_health.py",
        "model_design.py",
        "naming.py",
        "reuse.py",
        "task_sql_quality.py",
    }

    assert {path.name for path in (rules_dir / "engine").glob("*.py")} >= (
        expected_engine | {"__init__.py"}
    )
    assert {
        path.name for path in (rules_dir / "definitions").glob("*.py")
    } >= (expected_rule_modules | {"__init__.py"})
    assert {path.name for path in (rules_dir / "dimensions").glob("*.py")} >= (
        expected_rule_modules | {"__init__.py"}
    )
    assert not any(
        (rules_dir / name).exists() for name in expected_rule_modules
    )


def test_rule_definitions_do_not_execute_rules():
    from pathlib import Path

    definitions_dir = (
        Path(__file__).resolve().parents[2]
        / "assess"
        / "rules"
        / "definitions"
    )
    for path in definitions_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "RuleRunner" not in source
        assert ".run_rules(" not in source
        assert "def score_" not in source


def test_scoring_rule_wrappers_are_removed():
    from pathlib import Path

    scoring_dir = Path(__file__).resolve().parents[2] / "assess" / "scoring"
    removed_wrappers = {
        "asset_completeness.py",
        "depth.py",
        "metadata_health.py",
        "model_design.py",
        "naming.py",
        "reuse.py",
        "task_sql_quality.py",
    }

    assert not any((scoring_dir / name).exists() for name in removed_wrappers)


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
