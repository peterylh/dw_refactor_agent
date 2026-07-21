import pytest
import yaml

import dw_refactor_agent.config as config


def _execution():
    return {
        "materialized": "full",
        "full_refresh_strategy": "replace_all",
    }


def _v3_active():
    return {
        "version": 3,
        "name": "dws_example",
        "operational_layer": "DWS",
        "execution": _execution(),
        "layer": "DWS",
        "table_type": "fact",
        "business_process": "PAYMENT",
        "entities": [
            {
                "code": "CUSTOMER",
                "type": "primary",
                "key_columns": ["customer_id"],
            }
        ],
        "hierarchy_roles": [{"code": "CUSTOMER_LEVEL"}],
        "grain": {"keys": ["customer_id"]},
        "business_date": {"column": "event_date"},
        "degenerate_dimensions": ["order_number"],
        "atomic_metrics": [{"name": "event_count", "action": "COUNT"}],
        "metric_semantics": [{"name": "event_count", "unit": "events"}],
        "application_rules": [{"metric": "event_count", "scope": "daily"}],
    }


def _v3_quarantined():
    model = _v3_active()
    for fields in config.MODEL_SECTION_FIELDS.values():
        for field in fields:
            model.pop(field, None)
    model["governance"] = {
        "status": "quarantined",
        "schema_version": 1,
        "withheld_sections": list(config.MODEL_SECTIONS),
        "reasons": {
            "classification": ["structure_bundle_incomplete"],
            "business_semantics": ["business_process_missing"],
            "entities": ["structure_bundle_incomplete"],
            "grain": ["structure_bundle_incomplete"],
            "metrics": ["dependent_structure_unavailable"],
        },
    }
    return model


def test_v2_remains_active_and_legacy_aliases_are_read_only_normalized():
    raw = {
        "version": 2,
        "name": "dwd_legacy",
        "layer": "DWD",
        "table_type": "fact",
        "execution": {"materialized": "incremental"},
        "entity": {"code": "ORDER", "key_columns": ["order_id"]},
        "related_entities": [
            {
                "code": "CUSTOMER",
                "key_columns": ["customer_id"],
                "relationship": {"type": "many_to_one"},
            }
        ],
        "metrics": ["amount"],
    }

    model = config.validate_model_metadata(raw)

    assert model == raw
    assert config.get_operational_layer(model) == "DWD"
    assert config.get_semantic_layer(model) == "DWD"
    assert config.model_section_status(model, "metrics") == "active"
    assert config.get_execution_contract(model) == {
        "materialized": "incremental"
    }
    assert [item["type"] for item in config.get_entities(model)] == [
        "primary",
        "foreign",
    ]
    assert config.get_metrics(model)["atomic_metrics"] == [{"name": "amount"}]


def test_v2_extended_fact_types_keep_existing_metrics_active():
    raw = {
        "version": 2,
        "name": "dws_legacy_aggregate",
        "layer": "DWS",
        "table_type": "aggregate_fact",
        "derived_metrics": ["daily_amount"],
    }

    assert config.model_section_status(raw, "metrics") == "active"
    assert config.get_metrics(raw)["derived_metrics"] == ["daily_amount"]
    for alias, value in (
        ("entity", {"code": "ORDER"}),
        ("related_entities", [{"code": "CUSTOMER"}]),
    ):
        ods = {
            "version": 2,
            "name": f"ods_legacy_{alias}",
            "layer": "ODS",
            alias: value,
        }
        assert config.model_section_status(ods, "entities") == "active"
        assert config.get_entities(ods)[0]["code"] in {"ORDER", "CUSTOMER"}


def test_v3_withheld_sections_are_unavailable_but_operational_data_survives():
    model = config.validate_model_metadata(_v3_quarantined())

    assert config.get_operational_layer(model) == "DWS"
    assert config.get_execution_contract(model) == _execution()
    for section, accessor in (
        ("classification", config.get_semantic_layer),
        ("classification", config.get_table_type),
        ("business_semantics", config.get_business_semantics),
        ("entities", config.get_entities),
        ("grain", config.get_grain),
        ("metrics", config.get_metrics),
    ):
        value = accessor(model)
        assert isinstance(value, config.UnavailableModelSection)
        assert value.section == section
        assert config.model_section_status(model, section) == "quarantined"
        with pytest.raises(config.UnavailableModelSectionUsageError):
            bool(value)
        assert isinstance(
            config.get_semantic_section(model, section),
            config.UnavailableModelSection,
        )


def test_v3_without_governance_is_active_and_uses_canonical_fields():
    model = config.validate_model_metadata(_v3_active())

    assert config.get_semantic_layer(model) == "DWS"
    assert config.get_table_type(model) == "fact"
    assert config.get_business_semantics(model) == {
        "business_process": "PAYMENT"
    }
    assert config.get_entities(model)[0]["code"] == "CUSTOMER"
    assert config.get_grain(model) == {"keys": ["customer_id"]}
    metrics = config.get_metrics(model)
    assert metrics["atomic_metrics"][0]["name"] == "event_count"
    assert metrics["metric_semantics"][0]["unit"] == "events"
    assert metrics["application_rules"][0]["scope"] == "daily"
    entities = config.get_semantic_section(model, "entities")
    assert entities["hierarchy_roles"] == [{"code": "CUSTOMER_LEVEL"}]
    grain = config.get_semantic_section(model, "grain")
    assert grain["business_date"] == {"column": "event_date"}
    assert grain["degenerate_dimensions"] == ["order_number"]

    dimension = _v3_active()
    for field in config.MODEL_SECTION_FIELDS["metrics"]:
        dimension.pop(field, None)
    dimension.update(
        {
            "operational_layer": "DIM",
            "layer": "DIM",
            "table_type": "dimension",
            "dimension_role": "BASE",
            "dimension_content_type": "INFO",
            "dimension_policy": {"history": "snapshot"},
        }
    )
    classification = config.get_classification(dimension)
    assert classification["dimension_role"] == "BASE"
    assert classification["dimension_content_type"] == "INFO"
    assert classification["dimension_policy"] == {"history": "snapshot"}
    model["version"] = 4
    with pytest.raises(config.UnsupportedModelGovernanceError):
        config.get_operational_layer(model)


def test_unknown_or_inconsistent_governance_fails_closed():
    def rejected(model):
        with pytest.raises(config.UnsupportedModelGovernanceError):
            config.validate_model_metadata(model)

    for field, value in (
        ("status", "future"),
        ("schema_version", 2),
    ):
        model = _v3_quarantined()
        model["governance"][field] = value
        rejected(model)
    model = _v3_quarantined()
    model["governance"]["reasons"]["metrics"] = ["future"]
    rejected(model)

    model = _v3_quarantined()
    model["governance"]["withheld_sections"].append("future")
    model["governance"]["reasons"]["future"] = ["inspection_unavailable"]
    rejected(model)
    model = _v3_quarantined()
    model["governance"]["reasons"].pop("metrics")
    rejected(model)
    model = _v3_quarantined()
    model["governance"].update(
        {
            "withheld_sections": ["classification"],
            "reasons": {"classification": ["structure_bundle_incomplete"]},
        }
    )
    rejected(model)

    for field, value in (
        ("layer", "DWS"),
        ("metrics", ["amount"]),
    ):
        model = _v3_quarantined() if field == "layer" else _v3_active()
        model[field] = value
        rejected(model)
    model = _v3_active()
    model.update(
        {
            "operational_layer": "DIM",
            "layer": "DIM",
            "table_type": "dimension",
            "governance": {
                "status": "quarantined",
                "schema_version": 1,
                "withheld_sections": ["metrics"],
                "reasons": {"metrics": ["metrics_incomplete"]},
            },
        }
    )
    model.pop("atomic_metrics")
    rejected(model)
    rejected(
        {
            "version": 2,
            "name": "legacy",
            "layer": "DWD",
            "governance": {},
        }
    )


def test_registry_covers_scalar_and_mapping_forms_and_rejects_new_roots():
    for value in (
        "internal.orders",
        {"catalog": "internal", "table": "orders"},
    ):
        model = _v3_active()
        model["source"] = value
        assert config.unregistered_model_paths(model) == ()
        config.validate_model_metadata(model)
    for value in ("tenant_id = 1", {"column": "tenant_id"}):
        model = _v3_active()
        model["row_policy"] = value
        assert config.unregistered_model_paths(model) == ()
        config.validate_model_metadata(model)

    model = _v3_active()
    model["future_semantics"] = "unsafe"
    with pytest.raises(
        config.UnsupportedModelGovernanceError,
        match="unregistered model schema paths",
    ):
        config.validate_model_metadata(model)

    model = _v3_active()
    model["business_processes"] = [{"future_field": "unsafe"}]
    with pytest.raises(
        config.UnsupportedModelGovernanceError,
        match=r"business_processes\[\*\]\.future_field",
    ):
        config.validate_model_metadata(model)


def test_metric_applicability_uses_classification_and_accepts_scalar_items():
    fact = _v3_active()
    fact["atomic_metrics"] = ["event_count"]
    assert config.get_metrics(fact)["atomic_metrics"] == ["event_count"]

    dimension = _v3_active()
    for field in config.MODEL_SECTION_FIELDS["metrics"]:
        dimension.pop(field, None)
    dimension.update(
        {
            "operational_layer": "DIM",
            "layer": "DIM",
            "table_type": "dimension",
        }
    )
    assert config.model_section_status(dimension, "metrics") == (
        "not_applicable"
    )
    value = config.get_metrics(dimension)
    assert isinstance(value, config.NotApplicableModelSection)
    with pytest.raises(config.UnavailableModelSectionUsageError):
        bool(value)

    dimension["atomic_metrics"] = ["unsafe"]
    with pytest.raises(
        config.UnsupportedModelGovernanceError,
        match="not-applicable metrics section",
    ):
        config.validate_model_metadata(dimension)


def test_ods_sections_default_to_na_but_explicit_contracts_are_governed():
    default = {
        "version": 3,
        "name": "ods_orders",
        "operational_layer": "ODS",
        "execution": _execution(),
        "layer": "ODS",
        "table_type": "other",
    }
    for section in config.MODEL_SECTIONS[1:]:
        assert config.model_section_status(default, section) == (
            "not_applicable"
        )

    active = dict(default)
    active.update(
        {
            "business_process": "ORDER",
            "entities": [{"code": "ORDER"}],
            "grain": {"keys": ["order_id"]},
            "atomic_metrics": ["amount"],
        }
    )
    for section in config.MODEL_SECTIONS[1:]:
        assert config.model_section_status(active, section) == "active"
        assert isinstance(config.get_semantic_section(active, section), dict)
    for field, value in (
        ("business_process_mode", "composite"),
        ("business_process_sources", ["ods_order_items"]),
    ):
        explicit_business = dict(default)
        explicit_business[field] = value
        assert (
            config.model_section_status(
                explicit_business,
                "business_semantics",
            )
            == "active"
        )

    quarantined = dict(default)
    quarantined["governance"] = {
        "status": "quarantined",
        "schema_version": 1,
        "withheld_sections": list(config.MODEL_SECTIONS[1:]),
        "reasons": {
            "business_semantics": ["business_semantics_untrusted"],
            "entities": ["entities_incomplete"],
            "grain": ["grain_incomplete"],
            "metrics": ["metrics_incomplete"],
        },
    }
    for section in config.MODEL_SECTIONS[1:]:
        assert config.model_section_status(quarantined, section) == (
            "quarantined"
        )


def test_registry_covers_every_repository_model_path():
    model_paths = sorted(
        path
        for path in config.WAREHOUSES_ROOT.rglob("*.yaml")
        if "models" in path.parts
    )
    assert model_paths
    for path in model_paths:
        raw = (
            yaml.safe_load(path.read_text(encoding=config.TEXT_ENCODING)) or {}
        )
        assert config.unregistered_model_paths(raw) == (), path


def test_default_loader_validates_governance_and_raw_loader_is_explicit(
    monkeypatch,
    tmp_path,
):
    model_dir = tmp_path / "demo" / "mid" / "models"
    model_dir.mkdir(parents=True)
    path = model_dir / "dws_example.yaml"
    path.write_text(
        yaml.safe_dump(_v3_quarantined(), sort_keys=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG, "governed_demo", {"dir": "demo"}
    )
    config.clear_model_metadata_cache()

    governed = config.load_model_metadata("governed_demo")["dws_example"]
    raw = config.load_raw_model_metadata("governed_demo")[
        "mid/models/dws_example.yaml"
    ]

    assert isinstance(governed, config.GovernedModelMetadata)
    assert isinstance(
        config.get_model_layer("dws_example", "governed_demo"),
        (config.UnavailableModelSection),
    )
    assert (
        config.get_model_operational_layer("dws_example", "governed_demo")
        == "DWS"
    )
    assert config.get_model_names_by_operational_layer(
        "governed_demo", "DWS"
    ) == ["dws_example"]
    assert (
        config.determine_operational_layer("demo.DWS_Example", "governed_demo")
        == "DWS"
    )
    assert type(raw) is dict
    assert raw["governance"]["status"] == "quarantined"

    for document in (
        {"version": 3},
        {"version": 3, "name": ""},
        {"version": 3, "name": ["invalid"]},
        ["invalid"],
    ):
        path.write_text(
            yaml.safe_dump(document, sort_keys=False),
            encoding="utf-8",
        )
        assert config.load_raw_model_metadata("governed_demo") == {
            "mid/models/dws_example.yaml": document
        }
    config.clear_model_metadata_cache()
    with pytest.raises(config.UnsupportedModelGovernanceError):
        config.load_model_metadata("governed_demo")
    config.clear_model_metadata_cache()

    path.write_text(
        yaml.safe_dump(_v3_quarantined(), sort_keys=False),
        encoding="utf-8",
    )
    conflicting = _v3_quarantined()
    conflicting["name"] = "DWS_EXAMPLE"
    (model_dir / "conflicting.yaml").write_text(
        yaml.safe_dump(conflicting, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(
        config.UnsupportedModelGovernanceError,
        match="collide under case-insensitive lookup",
    ):
        config.load_model_metadata("governed_demo")
    config.clear_model_metadata_cache()
