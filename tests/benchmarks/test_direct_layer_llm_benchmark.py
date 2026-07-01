from types import SimpleNamespace

from benchmarks.direct_layer_llm.run import correct_no_layer_depth_from_ods


def test_correct_no_layer_depth_from_ods_recomputes_removed_ods_prefix():
    contexts = [
        SimpleNamespace(
            table_name="customer_source",
            upstream_tables=[],
            depth_from_ods=1,
        ),
        SimpleNamespace(
            table_name="customer_profile",
            upstream_tables=["customer_source"],
            depth_from_ods=2,
        ),
        SimpleNamespace(
            table_name="customer_rfm",
            upstream_tables=["customer_profile"],
            depth_from_ods=3,
        ),
        SimpleNamespace(
            table_name="external_seed",
            upstream_tables=[],
            depth_from_ods=1,
        ),
    ]
    mapping = {
        "ods_customer": "customer_source",
        "dim_customer": "customer_profile",
        "ads_customer_rfm": "customer_rfm",
    }
    expected = {
        "ods_customer": {"layer": "ODS"},
        "dim_customer": {"layer": "DIM"},
        "ads_customer_rfm": {"layer": "ADS"},
    }

    correct_no_layer_depth_from_ods(contexts, mapping, expected)

    depths = {ctx.table_name: ctx.depth_from_ods for ctx in contexts}
    assert depths == {
        "customer_source": 0,
        "customer_profile": 1,
        "customer_rfm": 2,
        "external_seed": 1,
    }
