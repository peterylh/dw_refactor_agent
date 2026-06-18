from assess.assessment_context import AssessmentContext
from assess.scoring.depth import score_lineage_depth
from assess.scoring.model_design import score_model_design_health
from assess.scoring.reuse import score_reusability


class _RawTable:
    def __init__(self, raw):
        self.raw = raw


class _FakeLineageView:
    def __init__(self, tables, upstream, downstream, table_edges):
        self._tables = tables
        self._upstream = upstream
        self._downstream = downstream
        self._table_edges = table_edges

    def tables(self):
        return [_RawTable(table) for table in self._tables]

    def asset_table_graph(self):
        return self._upstream, self._downstream

    def table_edge_source_files(self):
        return self._table_edges


def _check_by_rule(result, rule_id):
    return next(
        check for check in result["checks"] if check["rule_id"] == rule_id
    )


def test_assessment_context_derives_lineage_indexes_from_lineage_view():
    tables = [
        {"name": "ods_order", "layer": "ODS", "columns": []},
        {"name": "dwd_order_detail", "layer": "DWD", "columns": []},
        {"name": "ads_sales", "layer": "ADS", "columns": []},
    ]
    upstream = {
        "dwd_order_detail": {"ods_order"},
        "ads_sales": {"dwd_order_detail"},
    }
    downstream = {
        "ods_order": {"dwd_order_detail"},
        "dwd_order_detail": {"ads_sales"},
    }
    table_edges = {
        ("ods_order", "dwd_order_detail"): {"dwd_order_detail.sql"},
        ("dwd_order_detail", "ads_sales"): {"ads_sales.sql"},
    }
    context = AssessmentContext(
        project="unit",
        lineage=_FakeLineageView(tables, upstream, downstream, table_edges),
        assets={"tables": {}, "tasks": []},
    )

    assert context.tables == tables
    assert context.table_layers == {
        "ods_order": "ODS",
        "dwd_order_detail": "DWD",
        "ads_sales": "ADS",
    }
    assert context.upstream == upstream
    assert context.downstream == downstream
    assert context.table_edges == table_edges


def test_lineage_scorers_use_context_derived_graphs():
    tables = [
        {"name": "ods_order", "layer": "ODS", "columns": []},
        {
            "name": "dwd_order_detail",
            "layer": "DWD",
            "columns": [{"name": "order_id"}],
        },
        {"name": "ads_sales", "layer": "ADS", "columns": []},
    ]
    edges = [
        {
            "source": "ods_order.order_id",
            "target": "dwd_order_detail.order_id",
            "source_file": "dwd_order_detail.sql",
        },
        {
            "source": "dwd_order_detail.order_id",
            "target": "ads_sales.order_id",
            "source_file": "ads_sales.sql",
        },
    ]
    context = AssessmentContext.from_facts(
        project="unit",
        tables=tables,
        edges=edges,
        indirect_edges=[],
        models={},
        project_dir=None,
    )

    reuse = score_reusability(context)
    depth = score_lineage_depth(context)
    model_design = score_model_design_health(context)

    reuse_check = _check_by_rule(reuse, "REUSE_DOWNSTREAM_REACHES_TARGET")
    assert reuse_check["target"]["name"] == "dwd_order_detail"
    assert reuse_check["evidence"]["downstream_count"] == 1

    depth_check = _check_by_rule(depth, "DEPTH_MIDDLE_LAYER_IS_OPTIMAL")
    assert depth_check["target"]["name"] == "ads_sales"
    assert depth_check["evidence"]["max_middle_depth"] == 1

    assert {issue["rule_id"] for issue in model_design["issues"]} == {
        "ARCH_SKIP_LAYER_DEPENDENCY"
    }
