import lineage.lineage_extractor as lineage_extractor


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
