from __future__ import annotations

import pytest

from dw_refactor_agent.refactor.shadow_rewrite import (
    ReferenceRole,
    RelationRoute,
    RewriteContext,
    ShadowRewriteError,
    analyze_occurrences,
    rewrite_shadow_sql,
    unresolved_relations,
)


def test_analyze_occurrences_distinguishes_schema_and_data_reads():
    like_roles = [
        item.role
        for item in analyze_occurrences(
            "CREATE TABLE dm.tmp LIKE dm.renamed_sales;"
        )
    ]
    ctas_roles = [
        item.role
        for item in analyze_occurrences(
            "CREATE TABLE dm.tmp AS SELECT * FROM dm.renamed_sales;"
        )
    ]

    assert like_roles == [ReferenceRole.WRITE, ReferenceRole.SCHEMA_READ]
    assert ctas_roles == [ReferenceRole.WRITE, ReferenceRole.DATA_READ]


def test_analyze_occurrences_distinguishes_self_read_and_cte_local_refs():
    occurrences = analyze_occurrences(
        "INSERT INTO dm.sales "
        "WITH old_rows AS (SELECT * FROM dm.sales WHERE dt = @etl_date) "
        "SELECT * FROM old_rows;"
    )

    assert [(item.table, item.role) for item in occurrences] == [
        ("sales", ReferenceRole.WRITE),
        ("sales", ReferenceRole.DATA_READ),
        ("old_rows", ReferenceRole.LOCAL),
    ]


def test_delete_subquery_marks_only_delete_target_as_write():
    occurrences = analyze_occurrences(
        "DELETE FROM dm.sales WHERE store_id IN "
        "(SELECT store_id FROM dm.closed_stores);"
    )

    assert [(item.table, item.role) for item in occurrences] == [
        ("sales", ReferenceRole.WRITE),
        ("closed_stores", ReferenceRole.DATA_READ),
    ]


def test_merge_classifies_target_and_using_source():
    occurrences = analyze_occurrences(
        "MERGE INTO dm.sales t USING dm.sales_delta s "
        "ON t.id = s.id WHEN MATCHED THEN UPDATE SET amount = s.amount"
    )

    assert [(item.table, item.role) for item in occurrences] == [
        ("sales", ReferenceRole.WRITE),
        ("sales_delta", ReferenceRole.DATA_READ),
    ]


def test_explicit_routes_rewrite_full_relation_and_preserve_other_text():
    sql = (
        "-- keep dm.renamed_sales in this comment\n"
        "CREATE TABLE `dm`.`tmp_x` LIKE dm.renamed_sales;\n"
        "SELECT 'dm.renamed_sales';"
    )
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        write_routes={"tmp_x": RelationRoute("dm_qa", "tmp_x")},
        schema_routes={
            "renamed_sales": RelationRoute("dm_qa", "RENAMED_SALES")
        },
    )

    rewritten = rewrite_shadow_sql(sql, context)

    assert "CREATE TABLE `dm_qa`.`tmp_x` LIKE dm_qa.RENAMED_SALES" in rewritten
    assert "-- keep dm.renamed_sales in this comment" in rewritten
    assert "SELECT 'dm.renamed_sales'" in rewritten


def test_selected_data_read_without_route_fails_fast():
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        write_routes={"tmp_x": RelationRoute("dm_qa", "tmp_x")},
        selected_tables={"renamed_sales"},
        strict=True,
    )

    with pytest.raises(ShadowRewriteError, match="renamed_sales"):
        rewrite_shadow_sql(
            "CREATE TABLE dm.tmp_x AS SELECT * FROM dm.renamed_sales;",
            context,
        )


def test_explicit_qa_data_route_requires_runtime_readiness():
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        data_routes={"sales": RelationRoute("dm_qa", "sales")},
        selected_tables={"sales"},
        required_qa_tables={"sales"},
        strict=True,
    )

    with pytest.raises(ShadowRewriteError, match="not ready"):
        rewrite_shadow_sql("SELECT * FROM dm.sales;", context)

    context.qa_ready_tables.add("sales")
    assert rewrite_shadow_sql("SELECT * FROM dm.sales;", context) == (
        "SELECT * FROM dm_qa.sales;"
    )


def test_default_rewrite_routes_selected_like_source_to_qa():
    rewritten = rewrite_shadow_sql(
        "CREATE TABLE shop_dm.tmp_x LIKE shop_dm.I_SHOP_STORE_SALES_DS;",
        RewriteContext(
            prod_db="shop_dm",
            qa_db="shop_dm_qa",
            selected_tables={"I_SHOP_STORE_SALES_DS"},
        ),
    )

    assert rewritten == (
        "CREATE TABLE shop_dm_qa.tmp_x LIKE shop_dm_qa.I_SHOP_STORE_SALES_DS;"
    )


def test_default_rewrite_keeps_unselected_like_source_in_prod():
    rewritten = rewrite_shadow_sql(
        "CREATE TABLE shop_dm.tmp_x LIKE shop_dm.ods_sales;",
        RewriteContext(prod_db="shop_dm", qa_db="shop_dm_qa"),
    )

    assert rewritten == (
        "CREATE TABLE shop_dm_qa.tmp_x LIKE shop_dm.ods_sales;"
    )


def test_default_rewrite_keeps_ctas_source_in_prod_until_qa_ready():
    sql = (
        "CREATE TABLE shop_dm.tmp_x AS "
        "SELECT * FROM shop_dm.I_SHOP_STORE_SALES_DS;"
    )

    prod_read = rewrite_shadow_sql(
        sql,
        RewriteContext(prod_db="shop_dm", qa_db="shop_dm_qa"),
    )
    qa_read = rewrite_shadow_sql(
        sql,
        RewriteContext(
            prod_db="shop_dm",
            qa_db="shop_dm_qa",
            qa_ready_tables={"I_SHOP_STORE_SALES_DS"},
        ),
    )

    assert "FROM shop_dm.I_SHOP_STORE_SALES_DS" in prod_read
    assert "FROM shop_dm_qa.I_SHOP_STORE_SALES_DS" in qa_read


def test_explicit_routes_handle_unqualified_target_and_source():
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        write_routes={"tmp_x": RelationRoute("dm_qa", "tmp_x")},
        data_routes={"sales": RelationRoute("dm", "sales")},
    )

    rewritten = rewrite_shadow_sql(
        "INSERT INTO tmp_x SELECT * FROM sales;", context
    )

    assert rewritten == ("INSERT INTO dm_qa.tmp_x SELECT * FROM dm.sales;")


def test_created_helper_table_stays_local_to_qa_across_statements():
    sql = (
        "CREATE TABLE dm.stage LIKE dm.sales;\n"
        "INSERT INTO dm.stage SELECT * FROM dm.ods_sales;\n"
        "INSERT INTO dm.sales SELECT * FROM dm.stage;"
    )

    occurrences = analyze_occurrences(sql)
    stage_reads = [
        item
        for item in occurrences
        if item.table == "stage" and item.role is ReferenceRole.LOCAL
    ]
    rewritten = rewrite_shadow_sql(
        sql, RewriteContext(prod_db="dm", qa_db="dm_qa")
    )

    assert len(stage_reads) == 1
    assert stage_reads[0].physical is True
    assert "FROM dm_qa.stage" in rewritten
    assert "FROM dm.stage" not in rewritten


def test_comma_separated_data_sources_are_both_routed():
    rewritten = rewrite_shadow_sql(
        "INSERT INTO result SELECT * FROM left_source l, right_source r;",
        RewriteContext(prod_db="dm", qa_db="dm_qa"),
    )

    assert rewritten == (
        "INSERT INTO dm_qa.result "
        "SELECT * FROM dm.left_source l, dm.right_source r;"
    )


def test_metadata_and_view_references_are_classified_but_unknown_roles_surface():
    show = analyze_occurrences("SHOW CREATE TABLE dm.sales;")
    view = analyze_occurrences(
        "CREATE VIEW dm.sales_view AS SELECT * FROM dm.sales;"
    )

    assert [(item.table, item.role) for item in show] == [
        ("sales", ReferenceRole.SCHEMA_READ)
    ]
    assert [(item.table, item.role) for item in view] == [
        ("sales_view", ReferenceRole.WRITE),
        ("sales", ReferenceRole.DATA_READ),
    ]
    assert unresolved_relations("GRANT SELECT ON dm.sales TO bob;") == (
        "sales",
    )


def test_query_like_expression_is_not_a_schema_relation():
    occurrences = analyze_occurrences(
        "SELECT * FROM dm.customers WHERE name LIKE pattern_name;"
    )

    assert [(item.table, item.role) for item in occurrences] == [
        ("customers", ReferenceRole.DATA_READ)
    ]


def test_rename_table_rewrites_both_relations_and_opaque_commands_block():
    sql = "RENAME TABLE dm.sales TO dm.sales_new;"
    occurrences = analyze_occurrences(sql)
    rewritten = rewrite_shadow_sql(
        sql, RewriteContext(prod_db="dm", qa_db="dm_qa")
    )

    assert [(item.table, item.role) for item in occurrences] == [
        ("sales", ReferenceRole.WRITE),
        ("sales_new", ReferenceRole.WRITE),
    ]
    assert rewritten == "RENAME TABLE dm_qa.sales TO dm_qa.sales_new;"
    assert unresolved_relations("OPTIMIZE TABLE dm.sales;") == ("sales",)


def test_qualified_external_table_does_not_use_project_short_name_route():
    context = RewriteContext(
        prod_db="dm",
        qa_db="dm_qa",
        data_routes={"sales": RelationRoute("dm_qa", "sales")},
        selected_tables={"sales"},
        qa_ready_tables={"sales"},
    )

    rewritten = rewrite_shadow_sql(
        "SELECT * FROM reference_db.sales;", context
    )

    assert rewritten == "SELECT * FROM reference_db.sales;"
