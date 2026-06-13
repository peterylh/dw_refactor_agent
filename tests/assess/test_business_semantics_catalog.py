import yaml

import config
from assess.project_facts.business_semantics import (
    build_business_semantics_catalog_from_inspection,
    build_initial_business_semantics_catalog,
    business_semantics_path,
    write_initial_business_semantics_catalog,
)
from assess.table_inspector import TableInspectResult


def _configure_catalog_project(monkeypatch, tmp_path):
    project = "unit_catalog"
    project_dir = tmp_path / project
    (project_dir / "ddl").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        yaml.safe_dump(
            {
                "types": {},
                "bindings": {},
                "dictionaries": {
                    "data_domains": {
                        "values": [{
                            "id": "04",
                            "code": "TRAN",
                            "name": "交易域",
                            "keywords": ["order"],
                        }]
                    },
                    "business_areas": {
                        "values": [{
                            "id": "SHOP",
                            "code": "SHOP",
                            "name": "零售业务",
                            "keywords": ["order"],
                        }]
                    },
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "ddl" / "dwd_order_detail.sql").write_text(
        """
        CREATE TABLE dwd_order_detail (
            order_id BIGINT,
            order_item_id BIGINT,
            pay_amount DECIMAL(12,2)
        );
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {
        "dir": project,
        "naming_config": "naming_config.yaml",
    })
    config._naming_config_cache.clear()
    config._model_metadata_cache.clear()
    config._business_semantics_cache.clear()
    return project


def test_business_semantics_catalog_defaults_to_project_dir(
        tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)

    result = write_initial_business_semantics_catalog(project)

    catalog_path = tmp_path / project / "business_semantics.yaml"
    assert business_semantics_path(project) == catalog_path
    assert result["path"] == str(catalog_path)
    assert catalog_path.exists()

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    assert catalog["project"] == project
    assert catalog["data_domains"][0]["id"] == "04"
    assert catalog["business_areas"][0]["code"] == "SHOP"
    assert "mappings" not in catalog
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def test_build_initial_catalog_uses_project_tables(tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)

    catalog = build_initial_business_semantics_catalog(project)

    assert "mappings" not in catalog
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def test_build_catalog_from_inspection_clusters_llm_processes_and_subjects(
        tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)
    fact = TableInspectResult(
        table_name="dwd_transaction_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["明细事实"],
        inferred_data_domain="04",
        inferred_business_area="SHOP",
        columns={
            "atomic_metrics": [{
                "name": "pay_amount",
                "business_process": "TRANSACTION_EVENT",
            }],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )
    dimension = TableInspectResult(
        table_name="dwd_customer_profile",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.93,
        reasoning_steps=["客户实体属性"],
        inferred_data_domain="04",
        inferred_business_area="SHOP",
        entities=[{
            "code": "CUSTOMER",
            "type": "primary",
            "name": "客户",
            "key_columns": ["customer_id"],
        }],
    )

    catalog = build_business_semantics_catalog_from_inspection(
        project,
        [fact, dimension],
    )

    assert catalog["business_processes"] == [{
        "code": "TRANSACTION_EVENT",
        "name": "Transaction Event",
        "data_domain": "04",
        "business_area": "SHOP",
    }]
    assert catalog["semantic_subjects"] == [{
        "code": "CUSTOMER",
        "name": "客户",
        "data_domain": "04",
        "business_area": "SHOP",
    }]


def test_catalog_builder_does_not_turn_dimension_process_into_business_process(
        tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)
    dimension = TableInspectResult(
        table_name="dwd_entity_profile",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.9,
        reasoning_steps=[],
        columns={
            "atomic_metrics": [{
                "name": "entity_id",
                "business_process": "ENTITY_OPERATION",
            }],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
        entities=[{
            "code": "ENTITY",
            "type": "primary",
            "key_columns": ["entity_id"],
        }],
    )

    catalog = build_business_semantics_catalog_from_inspection(
        project,
        [dimension],
    )

    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"][0]["code"] == "ENTITY"


def test_catalog_builder_adds_llm_domain_and_area_candidates_without_dictionary(
        tmp_path, monkeypatch):
    project = "unit_catalog_empty_dict"
    project_dir = tmp_path / project
    (project_dir / "ddl").mkdir(parents=True)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(config.PROJECT_CONFIG, project, {
        "dir": project,
        "naming_config": "naming_config.yaml",
    })
    config._naming_config_cache.clear()
    config._business_semantics_cache.clear()
    result = TableInspectResult(
        table_name="dwd_event_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=[],
        inferred_data_domain="EVENT_DOMAIN",
        inferred_business_area="EVENT_ANALYTICS",
        columns={
            "atomic_metrics": [{
                "name": "event_amount",
                "business_process": "EVENT_COMPLETION",
            }],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )

    catalog = build_business_semantics_catalog_from_inspection(
        project,
        [result],
    )

    assert catalog["data_domains"] == [{
        "id": "EVENT_DOMAIN",
        "code": "EVENT_DOMAIN",
        "name": "Event Domain",
    }]
    assert catalog["business_areas"] == [{
        "id": "EVENT_ANALYTICS",
        "code": "EVENT_ANALYTICS",
        "name": "Event Analytics",
    }]
    assert catalog["business_processes"][0]["data_domain"] == "EVENT_DOMAIN"
    assert catalog["business_processes"][0]["business_area"] == "EVENT_ANALYTICS"


def test_write_initial_catalog_keeps_existing_without_overwrite(
        tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)
    catalog_path = tmp_path / project / "business_semantics.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [],
                "business_areas": [],
                "business_processes": [{
                    "code": "MANUAL",
                    "name": "人工维护",
                }],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = write_initial_business_semantics_catalog(project)

    assert result["changed"] is False
    assert result["catalog"]["business_processes"][0]["code"] == "MANUAL"


def test_get_business_domain_config_prefers_project_catalog(
        tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)
    catalog_path = tmp_path / project / "business_semantics.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [{
                    "id": "88",
                    "code": "CUST",
                    "name": "客户域",
                }],
                "business_areas": [{
                    "id": "CRM",
                    "code": "CRM",
                    "name": "客户经营",
                }],
                "business_processes": [],
                "semantic_subjects": [],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    business_config = config.get_business_domain_config(project)

    assert business_config.normalize_domain("CUST") == "88"
    assert business_config.normalize_business_area("CRM") == "CRM"
