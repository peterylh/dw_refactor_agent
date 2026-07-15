import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.assessment.project_facts.business_semantics import (
    build_business_semantics_catalog_from_inspection,
    build_initial_business_semantics_catalog,
    business_processes_path,
    business_semantics_dir,
    business_semantics_paths,
    business_taxonomy_path,
    semantic_subjects_path,
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
                "dictionaries": {},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "data_domains": [
                    {
                        "id": "04",
                        "code": "TRAN",
                        "name": "交易域",
                        "keywords": ["order"],
                    }
                ],
                "business_areas": [
                    {
                        "id": "SHOP",
                        "code": "SHOP",
                        "name": "零售业务",
                        "keywords": ["order"],
                    }
                ],
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
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()
    return project


def _write_split_catalog(project_dir, project, catalog):
    taxonomy = {
        "version": catalog.get("version", 1),
        "project": project,
        "data_domains": catalog.get("data_domains", []),
        "business_areas": catalog.get("business_areas", []),
    }
    if catalog.get("source"):
        taxonomy["source"] = catalog["source"]
    if catalog.get("project_context"):
        taxonomy["project_context"] = catalog["project_context"]
    (project_dir / "business_taxonomy.yaml").write_text(
        yaml.safe_dump(taxonomy, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (project_dir / "business_processes.yaml").write_text(
        yaml.safe_dump(
            {
                "version": catalog.get("version", 1),
                "project": project,
                "business_processes": catalog.get("business_processes", []),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "semantic_subjects.yaml").write_text(
        yaml.safe_dump(
            {
                "version": catalog.get("version", 1),
                "project": project,
                "semantic_subjects": catalog.get("semantic_subjects", []),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_business_semantics_catalog_defaults_to_project_dir(
    tmp_path, monkeypatch
):
    project = _configure_catalog_project(monkeypatch, tmp_path)

    result = write_initial_business_semantics_catalog(project)

    catalog_dir = tmp_path / project
    paths = business_semantics_paths(project)
    assert business_semantics_dir(project) == catalog_dir
    assert (
        business_taxonomy_path(project)
        == catalog_dir / "business_taxonomy.yaml"
    )
    assert (
        business_processes_path(project)
        == catalog_dir / "business_processes.yaml"
    )
    assert (
        semantic_subjects_path(project)
        == catalog_dir / "semantic_subjects.yaml"
    )
    assert result["path"] == str(catalog_dir)
    assert paths["taxonomy"].exists()
    assert paths["business_processes"].exists()
    assert paths["semantic_subjects"].exists()

    catalog = result["catalog"]
    assert catalog["project"] == project
    assert catalog["data_domains"][0]["id"] == "04"
    assert catalog["business_areas"][0]["code"] == "SHOP"
    assert "mappings" not in catalog
    assert catalog["business_processes"] == []
    assert catalog["semantic_subjects"] == []


def test_build_initial_catalog_does_not_fallback_to_naming_dictionaries(
    tmp_path, monkeypatch
):
    project = "unit_catalog_no_taxonomy"
    project_dir = tmp_path / project
    project_dir.mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        yaml.safe_dump(
            {
                "types": {},
                "bindings": {},
                "dictionaries": {
                    "data_domains": {
                        "values": [
                            {"id": "04", "code": "TRAN", "name": "交易域"}
                        ]
                    },
                    "business_areas": {
                        "values": [
                            {"id": "SHOP", "code": "SHOP", "name": "零售"}
                        ]
                    },
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    config.clear_naming_config_cache()
    config.clear_business_semantics_cache()

    catalog = build_initial_business_semantics_catalog(project)

    assert catalog["data_domains"] == []
    assert catalog["business_areas"] == []
    assert config.get_business_domain_config(project) is None


def test_build_catalog_from_inspection_clusters_llm_processes_and_subjects(
    tmp_path, monkeypatch
):
    project = _configure_catalog_project(monkeypatch, tmp_path)
    fact = TableInspectResult(
        table_name="dwd_transaction_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["明细事实"],
        inferred_data_domain="4",
        inferred_business_area="SHOP",
        columns={
            "atomic_metrics": [
                {
                    "name": "pay_amount",
                    "business_process": "TRANSACTION_EVENT",
                }
            ],
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
        entities=[
            {
                "code": "CUSTOMER",
                "type": "primary",
                "name": "客户",
                "key_columns": ["customer_id"],
            }
        ],
    )

    catalog = build_business_semantics_catalog_from_inspection(
        project,
        [fact, dimension],
    )

    assert catalog["business_processes"] == [
        {
            "code": "TRANSACTION_EVENT",
            "name": "Transaction Event",
            "data_domain": "04",
            "business_area": "SHOP",
        }
    ]
    assert catalog["semantic_subjects"] == [
        {
            "code": "CUSTOMER",
            "name": "客户",
            "data_domain": "04",
            "business_area": "SHOP",
        }
    ]


def _write_legacy_business_semantics_file(
    project_dir,
    project,
    *,
    context="旧目录背景",
    data_domain=None,
    business_area=None,
):
    legacy_path = project_dir / "business_semantics.yaml"
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": project,
                "source": "legacy",
                "project_context": context,
                "data_domains": [
                    data_domain
                    or {"id": "04", "code": "TRAN", "name": "交易域"}
                ],
                "business_areas": [
                    business_area
                    or {"id": "SHOP", "code": "SHOP", "name": "零售业务"}
                ],
                "business_processes": [
                    {"code": "ORDER_DETAIL", "name": "订单明细"}
                ],
                "semantic_subjects": [{"code": "CUSTOMER", "name": "客户"}],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return legacy_path


def test_write_initial_catalog_migrates_legacy_business_semantics_file(
    tmp_path, monkeypatch
):
    project = "unit_catalog_legacy_only"
    project_dir = tmp_path / project
    project_dir.mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    legacy_path = _write_legacy_business_semantics_file(
        project_dir,
        project,
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {"dir": project, "naming_config": "naming_config.yaml"},
    )
    config.clear_business_semantics_cache()
    config.clear_naming_config_cache()

    result = write_initial_business_semantics_catalog(project)

    assert result["written_names"] == [
        "business_processes",
        "semantic_subjects",
        "taxonomy",
    ]
    assert not legacy_path.exists()

    taxonomy = yaml.safe_load(
        (project_dir / "business_taxonomy.yaml").read_text(encoding="utf-8")
    )
    processes = yaml.safe_load(
        (project_dir / "business_processes.yaml").read_text(encoding="utf-8")
    )
    subjects = yaml.safe_load(
        (project_dir / "semantic_subjects.yaml").read_text(encoding="utf-8")
    )
    assert taxonomy["project_context"] == "旧目录背景"
    assert taxonomy["data_domains"][0]["id"] == "04"
    assert processes["business_processes"][0]["code"] == "ORDER_DETAIL"
    assert subjects["semantic_subjects"][0]["code"] == "CUSTOMER"

    project = _configure_catalog_project(monkeypatch, tmp_path)
    project_dir = tmp_path / project
    legacy_path = _write_legacy_business_semantics_file(
        project_dir,
        project,
        context="legacy context",
        data_domain={"id": "99", "code": "OLD", "name": "旧域"},
        business_area={"id": "OLD", "code": "OLD", "name": "旧业务"},
    )

    result = write_initial_business_semantics_catalog(project)

    assert result["written_names"] == [
        "business_processes",
        "semantic_subjects",
    ]
    assert not legacy_path.exists()

    taxonomy = yaml.safe_load(
        (project_dir / "business_taxonomy.yaml").read_text(encoding="utf-8")
    )
    processes = yaml.safe_load(
        (project_dir / "business_processes.yaml").read_text(encoding="utf-8")
    )
    subjects = yaml.safe_load(
        (project_dir / "semantic_subjects.yaml").read_text(encoding="utf-8")
    )
    assert taxonomy["data_domains"][0]["id"] == "04"
    assert "project_context" not in taxonomy
    assert processes["business_processes"][0]["code"] == "ORDER_DETAIL"
    assert subjects["semantic_subjects"][0]["code"] == "CUSTOMER"
