import yaml

import config
from assess.project_facts.business_semantics import (
    build_initial_business_semantics_catalog,
    business_semantics_path,
    write_initial_business_semantics_catalog,
)


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
    assert catalog["business_processes"][0]["tables"] == [
        "dwd_order_detail"
    ]


def test_build_initial_catalog_uses_project_tables(tmp_path, monkeypatch):
    project = _configure_catalog_project(monkeypatch, tmp_path)

    catalog = build_initial_business_semantics_catalog(project)

    assert "mappings" not in catalog
    assert catalog["business_processes"][0]["tables"] == [
        "dwd_order_detail"
    ]


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
                    "tables": [],
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
