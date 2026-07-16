import pytest
import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.assessment.llm.table_inspector import TableInspectResult
from dw_refactor_agent.config import (
    BusinessAreaDef,
    BusinessDomainConfig,
    DomainDef,
)


def _business_domain_config(*, domains=None, business_areas=None):
    return BusinessDomainConfig(
        domains=(
            {
                "04": DomainDef(id="04", code="TRAN", name="交易域"),
                "06": DomainDef(id="06", code="ORGN", name="机构域"),
            }
            if domains is None
            else domains
        ),
        business_areas=(
            {
                "CHNL": BusinessAreaDef(id="09", code="CHNL", name="渠道业务"),
                "PAYM": BusinessAreaDef(id="04", code="PAYM", name="支付结算"),
            }
            if business_areas is None
            else business_areas
        ),
    )


def _configure_project_root(monkeypatch, project_root):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    monkeypatch.setattr(config.core, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(writer_module, "PROJECT_ROOT", project_root)
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


def _write_split_catalog(project_dir, project, catalog):
    taxonomy = {
        "version": catalog.get("version", 1),
        "project": project,
        "data_domains": catalog.get("data_domains", []),
        "business_areas": catalog.get("business_areas", []),
    }
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


def _catalog_payload(
    *,
    domains=None,
    areas=None,
    processes=None,
    subjects=None,
):
    return {
        "version": 1,
        "data_domains": (
            domains
            if domains is not None
            else [{"id": "04", "code": "TRAN", "name": "交易域"}]
        ),
        "business_areas": (
            areas
            if areas is not None
            else [{"id": "SHOP", "code": "SHOP", "name": "零售业务"}]
        ),
        "business_processes": processes or [],
        "semantic_subjects": subjects or [],
    }


def _order_detail_process(code="ORDER_DETAIL"):
    return {
        "code": code,
        "name": "订单明细",
        "data_domain": "04",
        "business_area": "SHOP",
    }


def _customer_subject(code="CUSTOMER"):
    return {
        "code": code,
        "name": "客户",
        "data_domain": "04",
        "business_area": "SHOP",
    }


def _write_catalog_project(
    tmp_path,
    monkeypatch,
    project,
    *,
    catalog=None,
    ddl_tables=(),
    models=None,
):
    project_dir = tmp_path / project
    ddl_dir = project_dir / "mid" / "ddl"
    task_dir = project_dir / "mid" / "tasks"
    ddl_dir.mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    for table_name in ddl_tables:
        (ddl_dir / f"{table_name}.sql").write_text(
            (f"CREATE TABLE {table_name} (id BIGINT, customer_id BIGINT);\n"),
            encoding="utf-8",
        )
        (task_dir / f"{table_name}.sql").write_text(
            f"TRUNCATE TABLE {table_name};\n"
            f"INSERT INTO {table_name} SELECT 1, 1;\n",
            encoding="utf-8",
        )
    if models:
        models_dir = project_dir / "mid" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        for table_name, payload in models.items():
            (models_dir / f"{table_name}.yaml").write_text(
                yaml.safe_dump(
                    payload,
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
    if catalog is not None:
        _write_split_catalog(project_dir, project, catalog)
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    return project_dir


def _setup_catalog_discovery_model(
    tmp_path,
    monkeypatch,
    sample_lineage_data,
    project,
    *,
    model_text,
    inferred_data_domain,
    inferred_business_area,
):
    import dw_refactor_agent.assessment.llm.model_metadata_writer as writer_module

    project_dir = tmp_path / project
    (project_dir / "mid" / "ddl").mkdir(parents=True)
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir()
    (models_dir / "dwd_order_detail.yaml").write_text(
        model_text,
        encoding="utf-8",
    )
    (project_dir / "mid" / "tasks").mkdir()
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\ndictionaries: {}\n",
        encoding="utf-8",
    )
    _write_split_catalog(project_dir, project, _catalog_payload())
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    data = dict(sample_lineage_data)
    data["tables"] = [
        table
        for table in sample_lineage_data["tables"]
        if table["name"] == "dwd_order_detail"
    ]
    monkeypatch.setattr(writer_module, "load_lineage_data", lambda _: data)

    class FakeInspector:
        def __init__(
            self, api_key, *, model, cache_file, max_retries, parallelism
        ):
            self.progress_callback = None

        def inspect_batch(self, contexts):
            return [
                TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="DWD",
                    table_type="fact",
                    confidence=0.9,
                    reasoning_steps=[],
                    inferred_data_domain=inferred_data_domain,
                    inferred_business_area=inferred_business_area,
                    columns={
                        "atomic_metrics": [
                            {
                                "name": "subtotal",
                                "business_process": "ORDER_TRANSACTION",
                            }
                        ],
                        "derived_metrics": [],
                        "calculated_metrics": [],
                        "dimensions": [],
                        "others": [],
                    },
                )
                for ctx in contexts
            ]

    monkeypatch.setattr(writer_module, "TableInspector", FakeInspector)
    return models_dir


@pytest.fixture
def isolated_writer_project(tmp_path, monkeypatch):
    project = "unit_writer"
    project_dir = tmp_path / project
    models_dir = project_dir / "mid" / "models"
    models_dir.mkdir(parents=True)
    for table_name, layer in [
        ("dwd_customer", "DWD"),
        ("dwd_order_detail", "DWD"),
        ("dws_store_sales_daily", "DWS"),
        ("ads_sales_dashboard", "ADS"),
        ("dim_store", "DIM"),
    ]:
        (models_dir / f"{table_name}.yaml").write_text(
            f"version: 2\nname: {table_name}\nlayer: {layer}\n",
            encoding="utf-8",
        )
    (tmp_path / "naming_config.yaml").write_text(
        "types: {}\nbindings: {}\n",
        encoding="utf-8",
    )
    _configure_project_root(monkeypatch, tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        project,
        {
            "dir": project,
            "naming_config": "naming_config.yaml",
        },
    )
    yield project
    config.clear_naming_config_cache()
    config.clear_model_metadata_cache()
    config.clear_business_semantics_cache()


def _sample_fact_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="dwd_order_detail",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="fact",
        confidence=0.91,
        reasoning_steps=["订单明细事实表"],
        columns={
            "atomic_metrics": [
                {
                    "name": "pay_amt",
                    "data_type": "DECIMAL(12,2)",
                    "business_process": "订单支付",
                    "action": "pay",
                    "measure": "amt",
                    "description": "支付金额",
                    "reason": "基础支付金额",
                    "confidence": 0.95,
                }
            ],
            "derived_metrics": [
                {
                    "name": "pay_amt_1d",
                    "data_type": "DECIMAL(12,2)",
                    "base_metric": "pay_amt",
                    "base_metric_table": "dwd_order_detail",
                    "modifiers": [],
                    "time_period": "1d",
                    "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
                    "description": "近 1 日支付金额",
                    "reason": "原子指标加时间周期限定",
                    "confidence": 0.86,
                }
            ],
            "calculated_metrics": [
                {
                    "name": "gross_profit",
                    "data_type": "DECIMAL(12,2)",
                    "expression": "subtotal - cost_price * quantity",
                    "derived_from": ["subtotal", "cost_price", "quantity"],
                    "description": "毛利",
                    "reason": "多字段计算得到",
                    "confidence": 0.88,
                }
            ],
            "dimensions": [
                {
                    "name": "order_id",
                    "dimension_type": "primary_key",
                    "data_type": "BIGINT",
                    "confidence": 0.9,
                }
            ],
            "others": [
                {
                    "name": "etl_time",
                    "role": "audit",
                    "data_type": "DATETIME",
                    "confidence": 0.9,
                }
            ],
        },
    )


def _sample_dws_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="dws_store_sales_daily",
        declared_layer="DWS",
        inferred_layer="DWS",
        table_type="fact",
        confidence=0.9,
        reasoning_steps=["门店日销售汇总事实表"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [
                {
                    "name": "sale_amount",
                    "data_type": "DECIMAL(14,2)",
                    "base_metric": "subtotal",
                    "base_metric_table": "dwd_order_detail",
                    "modifiers": ["store"],
                    "time_period": "1d",
                    "expression": "SUM(subtotal) GROUP BY store_id, order_date",
                    "description": "门店日销售金额",
                    "reason": "原子指标按门店和日期汇总",
                    "confidence": 0.9,
                }
            ],
            "calculated_metrics": [],
            "dimensions": [
                {
                    "name": "store_id",
                    "dimension_type": "foreign_key",
                    "data_type": "BIGINT",
                    "confidence": 0.9,
                }
            ],
            "others": [],
        },
    )


def _sample_dimension_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="M_SHOP_06_STORE_DF",
        declared_layer="DWD",
        inferred_layer="DIM",
        table_type="dimension",
        confidence=0.93,
        reasoning_steps=["门店实体属性快照，适合作为公共维度"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [
                {
                    "name": "STORE_ID",
                    "dimension_type": "primary_key",
                    "data_type": "BIGINT",
                    "confidence": 0.95,
                }
            ],
            "others": [],
        },
    )


def _sample_dimension_conflict_result() -> TableInspectResult:
    return TableInspectResult(
        table_name="M_SHOP_06_STORE_DF",
        declared_layer="DWD",
        inferred_layer="DWD",
        table_type="dimension",
        confidence=0.88,
        reasoning_steps=["表类型是维度表，但分层判断仍返回 DWD"],
        columns={
            "atomic_metrics": [],
            "derived_metrics": [],
            "calculated_metrics": [],
            "dimensions": [],
            "others": [],
        },
    )


def _expected_pay_amt_1d_metric() -> dict:
    return {
        "name": "pay_amt_1d",
        "base_metric": "pay_amt",
        "base_metric_table": "dwd_order_detail",
        "aggregation": "SUM",
        "time_period": "D",
        "expression": "SUM(pay_amt) WHERE pay_date = @etl_date",
    }


def _run_isolated_writer_helper(tmp_path_factory, monkeypatch, helper):
    with monkeypatch.context() as isolated_monkeypatch:
        tmp_path = tmp_path_factory.mktemp(
            helper.__name__.replace("_assert_", "")
        )
        helper(tmp_path, isolated_monkeypatch)
