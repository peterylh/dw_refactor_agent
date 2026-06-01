import yaml

from assess.metric_detector import (
    build_dwd_contexts,
    metric_groups_for_model,
    metric_violations,
    metric_names_for_model,
    run_detection,
    update_model_yaml,
)
from assess.table_inspector import TableInspectResult


def _sample_fact_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["订单明细事实表"],
        columns={
            "atomic_metrics": [{
                "name": "pay_amt",
                "data_type": "DECIMAL(12,2)",
                "business_process": "订单支付",
                "action": "pay",
                "measure": "amt",
                "description": "支付金额",
                "reason": "基础支付金额",
                "confidence": 0.95,
            }],
            "derived_metrics": [{
                "name": "gross_profit",
                "data_type": "DECIMAL(12,2)",
                "expression": "subtotal - cost_price * quantity",
                "derived_from": ["subtotal", "cost_price", "quantity"],
                "description": "毛利",
                "reason": "多字段计算得到",
                "confidence": 0.88,
            }],
            "dimensions": [{
                "name": "order_id",
                "dimension_type": "primary_key",
                "data_type": "BIGINT",
                "confidence": 0.9,
            }],
            "others": [{
                "name": "etl_time",
                "role": "audit",
                "data_type": "DATETIME",
                "confidence": 0.9,
            }],
        },
    )


def test_build_dwd_contexts_filters_out_non_dwd(sample_lineage_data):
    contexts = build_dwd_contexts("shop", sample_lineage_data)

    assert {ctx.table_name for ctx in contexts} == {
        "dwd_customer",
        "dwd_order_detail",
    }


def test_metric_names_for_model_includes_atomic_and_derived_metrics():
    metrics = metric_names_for_model(_sample_fact_result())

    assert metrics == ["pay_amt", "gross_profit"]


def test_metric_groups_for_model_splits_atomic_and_derived_metrics():
    metric_groups = metric_groups_for_model(_sample_fact_result())

    assert metric_groups == {
        "atomic_metrics": ["pay_amt"],
        "derived_metrics": ["gross_profit"],
    }


def test_metric_violations_uses_derived_group_only():
    violations = metric_violations(_sample_fact_result())

    assert violations == [{
        "table": "dwd_order_detail",
        "column": "gross_profit",
        "metric_type": "derived",
        "reason": "多字段计算得到",
        "confidence": 0.88,
    }]


def test_metric_violations_skips_non_fact():
    result = TableInspectResult(
        table_name="dwd_customer",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [{"name": "age_group"}],
            "dimensions": [],
            "others": [],
        },
    )

    assert metric_violations(result) == []


def test_update_model_yaml_preserves_existing_metadata(tmp_path, monkeypatch):
    import assess.metric_detector as detector_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump({
            "version": 2,
            "name": "dwd_order_detail",
            "layer": "DWD",
            "description": "订单明细事实表",
            "config": {
                "materialized": "incremental",
            },
        },
                       allow_unicode=True,
                       sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(detector_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(detector_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 2
    assert update["new_metric_count"] == 2
    assert saved["description"] == "订单明细事实表"
    assert saved["config"]["materialized"] == "incremental"
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def test_update_model_yaml_replaces_existing_metrics(tmp_path, monkeypatch):
    import assess.metric_detector as detector_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump({
            "version": 2,
            "name": "dwd_order_detail",
            "layer": "DWD",
            "metrics": ["existing_metric", "pay_amt"],
        },
                       allow_unicode=True,
                       sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(detector_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(detector_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 2
    assert update["new_metric_count"] == 1
    assert update["removed_metric_count"] == 1
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def test_update_model_yaml_replaces_legacy_metric_fields(tmp_path, monkeypatch):
    import assess.metric_detector as detector_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_order_detail.yaml"
    model_path.write_text(
        yaml.safe_dump({
            "version": 2,
            "name": "dwd_order_detail",
            "layer": "DWD",
            "atomic_metrics": [{"name": "legacy_atomic"}],
        },
                       allow_unicode=True,
                       sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(detector_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(detector_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml("demo", _sample_fact_result())
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 2
    assert update["new_metric_count"] == 2
    assert update["removed_metric_count"] == 1
    assert saved["atomic_metrics"] == ["pay_amt"]
    assert saved["derived_metrics"] == ["gross_profit"]
    assert "metrics" not in saved


def test_update_model_yaml_removes_metrics_when_none_detected(tmp_path,
                                                              monkeypatch):
    import assess.metric_detector as detector_module

    project_root = tmp_path
    models_dir = project_root / "demo" / "models"
    models_dir.mkdir(parents=True)
    model_path = models_dir / "dwd_accounts.yaml"
    model_path.write_text(
        yaml.safe_dump({
            "version": 2,
            "name": "dwd_accounts",
            "layer": "DWD",
            "metrics": ["current_balance"],
        },
                       allow_unicode=True,
                       sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(detector_module, "PROJECT_ROOT", project_root)
    monkeypatch.setitem(detector_module.PROJECT_CONFIG, "demo", {"dir": "demo"})

    update = update_model_yaml(
        "demo",
        TableInspectResult(
            table_name="dwd_accounts",
            declared_layer="DWD",
            inferred_layer="DWD",
            table_type="dimension",
            confidence=0.9,
            reasoning_steps=[],
        ),
    )
    saved = yaml.safe_load(model_path.read_text(encoding="utf-8"))

    assert update["metric_count"] == 0
    assert update["removed_metric_count"] == 1
    assert update["updated"] is True
    assert "metrics" not in saved


def test_run_detection_reuses_table_inspector(monkeypatch, sample_lineage_data):
    import assess.metric_detector as detector_module

    class FakeInspector:
        def __init__(self, api_key, *, model, cache_file, max_retries,
                     parallelism):
            self.api_key = api_key
            self.model = model
            self.cache_file = cache_file
            self.max_retries = max_retries
            self.parallelism = parallelism

        def inspect_batch(self, contexts):
            return [
                _sample_fact_result(),
                TableInspectResult(
                    table_name="dwd_customer",
                    declared_layer="DWD",
                    inferred_layer="DIM",
                    table_type="dimension",
                    confidence=0.9,
                    reasoning_steps=[],
                ),
            ]

    monkeypatch.setattr(detector_module, "load_lineage_data",
                        lambda project: sample_lineage_data)
    monkeypatch.setattr(detector_module, "TableInspector", FakeInspector)

    result = run_detection("shop", api_key="test", dry_run=True)

    assert result["dwd_table_count"] == 2
    assert result["fact_table_count"] == 1
    assert result["atomic_metric_count"] == 1
    assert result["metric_count"] == 2
    assert result["derived_metric_violation_count"] == 1
    assert result["model_updates"][0]["updated"] is False
    assert result["skipped_model_updates"] == []


def test_run_detection_passes_parallelism(monkeypatch, sample_lineage_data):
    import assess.metric_detector as detector_module

    seen = {}

    class FakeInspector:
        def __init__(self, api_key, *, model, cache_file, max_retries,
                     parallelism):
            seen["parallelism"] = parallelism

        def inspect_batch(self, contexts):
            return []

    monkeypatch.setattr(detector_module, "load_lineage_data",
                        lambda project: sample_lineage_data)
    monkeypatch.setattr(detector_module, "TableInspector", FakeInspector)

    run_detection("shop", api_key="test", dry_run=True, parallelism=4)

    assert seen["parallelism"] == 4


def test_run_detection_skips_blocked_model_updates(monkeypatch, sample_lineage_data):
    import assess.metric_detector as detector_module

    blocked = _sample_fact_result()
    blocked.validation = {
        "unknown_columns": ["ghost_amt"],
        "duplicate_columns": [],
        "missing_columns": [],
    }

    class FakeInspector:
        def __init__(self, api_key, *, model, cache_file, max_retries,
                     parallelism):
            pass

        def inspect_batch(self, contexts):
            return [blocked]

    monkeypatch.setattr(detector_module, "load_lineage_data",
                        lambda project: sample_lineage_data)
    monkeypatch.setattr(detector_module, "TableInspector", FakeInspector)

    result = run_detection("shop", api_key="test", dry_run=True)

    assert result["blocked_table_count"] == 1
    assert result["model_updates"] == []
    assert result["skipped_model_updates"][0]["table"] == "dwd_order_detail"
    assert result["skipped_model_updates"][0]["reason"] == "validation_blocked"
