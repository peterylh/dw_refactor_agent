import logging

import dw_refactor_agent.lineage.lineage_extractor as lineage_extractor


def test_format_layer_statistics_summarizes_without_table_names(monkeypatch):
    layers = {
        "ods_customer": "ODS",
        "ods_order": "ODS",
        "dwd_order_detail": "DWD",
        "dim_date": "DIM",
    }
    monkeypatch.setattr(
        lineage_extractor,
        "determine_layer",
        lambda table_name: layers.get(table_name, "OTHER"),
    )
    tables = [
        {
            "name": "ods_customer",
            "columns": [{"name": "customer_id"}, {"name": "customer_name"}],
        },
        {
            "name": "ods_order",
            "columns": [{"name": "order_id"}],
        },
        {
            "name": "dwd_order_detail",
            "columns": [{"name": "order_id"}, {"name": "payment_amount"}],
        },
        {
            "name": "dim_date",
            "columns": [{"name": "date_key"}],
        },
        {
            "name": "tmp_stage",
            "columns": [],
        },
    ]

    lines = lineage_extractor.format_layer_statistics(tables)

    assert lines == [
        "分层统计:",
        "  ODS: 2 个表, 3 个字段",
        "  DWD: 1 个表, 2 个字段",
        "  DWS: 0 个表, 0 个字段",
        "  DIM: 1 个表, 1 个字段",
        "  ADS: 0 个表, 0 个字段",
        "  OTHER: 1 个表, 0 个字段",
    ]
    assert not any("ods_customer" in line for line in lines)
    assert not any("dwd_order_detail" in line for line in lines)


def test_format_lineage_output_statistics_counts_dataset_types_and_warnings():
    output = {
        "tables": [
            {
                "dataset_type": "managed",
                "columns": [{"name": "id"}],
            },
            {
                "dataset_type": "process",
                "columns": [{"name": "id"}, {"name": "amount"}],
            },
            {"dataset_type": "temporary", "columns": []},
            {"dataset_type": "external", "columns": []},
        ],
        "edges": [
            {"relation_type": "direct"},
            {"relation_type": "group_by"},
        ],
        "diagnostics": [{"code": "warning-a"}, {"code": "warning-b"}],
    }

    assert lineage_extractor.format_lineage_output_statistics(output) == [
        "  直接血缘: 1 条边",
        "  间接血缘: 1 条边",
        "  节点数: 3",
        "  表数: 4",
        "  数据集类型: managed=1, process=1, temporary=1, external=1",
        "  生产者警告: 2",
    ]


def test_format_lineage_output_statistics_deduplicates_multiple_producer_warning():
    output = {
        "tables": [],
        "edges": [],
        "jobs": [
            {"name": "job_a", "outputs": ["internal.demo_dm.shared"]},
            {"name": "job_b", "outputs": ["INTERNAL.DEMO_DM.SHARED"]},
        ],
        "diagnostics": [
            {
                "reason": "multiple_candidates",
                "dataset": "internal.demo_dm.shared",
            }
        ],
    }

    assert lineage_extractor.format_lineage_output_statistics(output)[-1] == (
        "  生产者警告: 1"
    )


def test_warn_multiple_producer_datasets_logs_actionable_warning(caplog):
    jobs = [
        {"name": "job_b", "outputs": ["internal.demo_dm.shared"]},
        {"name": "job_a", "outputs": ["INTERNAL.DEMO_DM.SHARED"]},
    ]

    with caplog.at_level(logging.WARNING):
        lineage_extractor.warn_multiple_producer_datasets(jobs)

    assert [record.levelno for record in caplog.records] == [logging.WARNING]
    assert [record.getMessage() for record in caplog.records] == [
        "数据集 internal.demo_dm.shared 由多个作业生产: job_a, job_b"
    ]
