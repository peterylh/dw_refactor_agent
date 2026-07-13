from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT / "warehouses" / "retail_banking"
SPEC_PATH = PROJECT_ROOT / "semantic_specs" / "dws_ads.yaml"
BENCHMARK_CONTRACT_PATH = (
    PROJECT_ROOT / "benchmark" / "benchmark_contract.yaml"
)

METRIC_KEYS = {
    "name",
    "class",
    "formula",
    "unit",
    "currency_source",
    "aggregation_behavior",
    "additive_over",
    "sign",
    "reversal",
}
TABLE_KEYS = {
    "current_name",
    "name",
    "decision",
    "source",
    "canonical_process",
    "business_date",
    "grain",
    "entities",
    "degenerate_dimensions",
    "metrics",
}


def _load_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _ddl_stems(directory, prefix):
    return {path.stem for path in directory.glob("{}*.sql".format(prefix))}


def _assert_no_null_mapping_keys(value):
    if isinstance(value, dict):
        assert None not in value
        for item in value.values():
            _assert_no_null_mapping_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_null_mapping_keys(item)


def test_semantic_spec_covers_every_generated_dws_and_ads_table():
    spec = _load_yaml(SPEC_PATH)
    expected_dws = _ddl_stems(PROJECT_ROOT / "mid" / "ddl", "dws_")
    expected_ads = _ddl_stems(PROJECT_ROOT / "ads" / "ddl", "ads_")

    assert len(spec["dws"]) == 18
    assert len(spec["ads"]) == 13
    assert {item["name"] for item in spec["dws"]} == expected_dws
    assert {item["name"] for item in spec["ads"]} == expected_ads


def test_semantic_spec_has_complete_financial_metric_contracts():
    spec = _load_yaml(SPEC_PATH)
    _assert_no_null_mapping_keys(spec)
    final_names = []

    for layer in ("dws", "ads"):
        for table in spec[layer]:
            assert set(table) >= TABLE_KEYS
            assert table["decision"] in {"accept", "revise", "reject"}
            assert table["source"]
            assert table["business_date"]["column"]
            assert table["business_date"]["kind"]
            assert table["grain"]["columns"]
            assert isinstance(table["entities"], list)
            assert isinstance(table["degenerate_dimensions"], list)
            assert table["metrics"]
            final_names.append(table["name"])

            metric_names = []
            for metric in table["metrics"]:
                assert set(metric) >= METRIC_KEYS
                assert metric["class"] in {
                    "atomic",
                    "derived",
                    "calculated",
                }
                assert metric["aggregation_behavior"] in {
                    "additive",
                    "semi_additive",
                    "non_additive",
                }
                assert isinstance(metric["additive_over"], list)
                assert metric["formula"]
                if metric["aggregation_behavior"] == "non_additive":
                    assert metric["additive_over"] == []
                if "currency" in metric["unit"]:
                    assert metric["currency_source"] != "not_applicable"
                metric_names.append(metric["name"])
            assert len(metric_names) == len(set(metric_names))

    assert len(final_names) == len(set(final_names))


def test_semantic_spec_sources_resolve_to_physical_or_canonical_assets():
    spec = _load_yaml(SPEC_PATH)
    dim_dwd = _load_yaml(PROJECT_ROOT / "semantic_specs" / "dim_dwd.yaml")
    aliases = {
        item["current_target"]: item["target_table"]
        for item in dim_dwd["entries"]
        if item.get("current_target") and item.get("target_table")
    }
    physical_assets = {
        path.stem
        for path in (
            list((PROJECT_ROOT / "mid" / "ddl").glob("*.sql"))
            + list((PROJECT_ROOT / "ads" / "ddl").glob("*.sql"))
        )
    }
    canonical_assets = {
        table["name"] for layer in ("dws", "ads") for table in spec[layer]
    }

    for layer in ("dws", "ads"):
        for table in spec[layer]:
            resolved_sources = {
                aliases.get(source, source) for source in table["source"]
            }
            assert resolved_sources <= physical_assets | canonical_assets
            grain_columns = set(table["grain"]["columns"])
            assert all(
                entity["key"] in grain_columns for entity in table["entities"]
            )


def test_canonical_processes_are_closed_over_business_process_catalog():
    spec = _load_yaml(SPEC_PATH)
    catalog = _load_yaml(PROJECT_ROOT / "business_processes.yaml")
    valid_codes = {
        item["code"] for item in catalog.get("business_processes") or []
    }
    used_codes = {
        table["canonical_process"]
        for layer in ("dws", "ads")
        for table in spec[layer]
    }

    assert used_codes <= valid_codes


def test_ads_have_application_rules_and_monitor_names_have_real_rules():
    spec = _load_yaml(SPEC_PATH)
    monitor_rule_kinds = {"status_monitor", "reconciliation", "anomaly"}

    for table in spec["ads"]:
        rules = table.get("application_rules") or []
        assert rules
        for rule in rules:
            assert {"name", "kind", "formula", "purpose"} <= set(rule)
        if "monitor" in table["name"]:
            assert any(rule["kind"] in monitor_rule_kinds for rule in rules)


def test_revised_overstated_monitor_names_are_not_canonical_names():
    spec = _load_yaml(SPEC_PATH)
    revised_monitors = {
        table["current_name"]: table["name"]
        for table in spec["ads"]
        if table["decision"] == "revise" and "monitor" in table["current_name"]
    }

    assert len(revised_monitors) == 10
    assert all(
        "monitor" not in final_name
        for current_name, final_name in revised_monitors.items()
        if current_name != "ads_provision_posting_monitor_daily"
    )
    assert (
        revised_monitors["ads_provision_posting_monitor_daily"]
        == "ads_provision_posting_monitor_daily"
    )


def test_benchmark_contract_defines_private_role_blind_scoring():
    schema = _load_yaml(BENCHMARK_CONTRACT_PATH)

    assert schema["private_gold"] is True
    assert "semantic_specs" in schema["public_input_must_exclude"]
    assert (
        "benchmark/benchmark_contract.yaml"
        in schema["public_input_must_exclude"]
    )
    assert schema["tracks"]["prefixless_role_blind"]["role_blind"] is True
    assert schema["tracks"]["partially_obfuscated"]["role_blind"] is True
    assert (
        "allowed_alternatives" in schema["table_record"]["fields"]["expected"]
    )

    dimensions = schema["scoring"]["dimensions"]
    assert {
        "layer",
        "table_type",
        "domain",
        "process",
        "entities",
        "grain",
        "metric_class",
        "metric_formula",
        "metric_behavior",
        "sensitivity",
    } == set(dimensions)
    assert (
        abs(sum(item["weight"] for item in dimensions.values()) - 1.0) < 1e-9
    )
    assert {
        "restricted_column_leak",
        "cross_currency_sum_without_currency_partition",
        "balance_metric_marked_fully_additive_over_time",
        "reversal_double_count",
        "fabricated_field_or_source",
    } == set(schema["scoring"]["hard_failures"])
