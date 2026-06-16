import sqlglot
from sqlglot import exp

from lineage.lineage_extractor import update_to_select


def _convert(sql: str) -> exp.Select:
    update = sqlglot.parse_one(sql, dialect="doris")
    select = update_to_select(update)
    assert isinstance(select, exp.Select)
    return select


def _projection_aliases(select: exp.Select) -> list[str]:
    return [expression.alias_or_name for expression in select.expressions]


def test_update_to_select_maps_set_items_to_projection_aliases():
    select = _convert(
        "UPDATE t SET a = 1, b = 2, c = a + b WHERE flag = 1"
    )

    assert _projection_aliases(select) == ["a", "b", "c"]
    assert select.args["from_"].this.name == "t"
    assert select.args.get("where") is not None


def test_update_to_select_preserves_database_qualified_target_table():
    select = _convert("UPDATE shop_dm.dwd_customer SET member_level = '金卡'")
    source_table = select.args["from_"].this

    assert source_table.name == "dwd_customer"
    assert source_table.db == "shop_dm"
    assert _projection_aliases(select) == ["member_level"]


def test_update_to_select_keeps_column_and_case_dependencies_in_projection():
    column_select = _convert("UPDATE t SET a = b")
    case_select = _convert("""
        UPDATE t SET col = CASE WHEN x > 0 THEN 1 ELSE col END
    """)

    assert isinstance(column_select.expressions[0].this, exp.Column)
    assert isinstance(case_select.expressions[0].this, exp.Case)


def test_update_to_select_preserves_join_sources_and_join_condition():
    select = _convert("UPDATE t JOIN s ON t.id = s.id SET t.a = s.b")
    joins = select.args.get("joins") or []

    assert select.args["from_"].this.name == "t"
    assert len(joins) == 1
    assert joins[0].this.name == "s"
    assert joins[0].args.get("on") is not None
    assert _projection_aliases(select) == ["a"]


def test_update_to_select_omits_where_when_update_has_no_filter():
    select = _convert("UPDATE t SET a = 1")

    assert select.args.get("where") is None
