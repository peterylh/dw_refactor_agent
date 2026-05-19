import sqlglot
from sqlglot import exp
from lineage.lineage_extractor import update_to_select


def _parse_update(sql):
    return sqlglot.parse_one(sql, dialect="doris")


class TestUpdateToSelect:
    def test_simple_set(self):
        update = _parse_update("UPDATE t SET col1 = 1, col2 = 'abc'")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "SELECT" in sql
        assert "1 AS col1" in sql or "1 AS col1" in sql
        assert "'abc' AS col2" in sql
        assert "FROM t" in sql

    def test_set_with_table_ref(self):
        update = _parse_update("UPDATE shop_dm.dwd_customer SET member_level = '金卡'")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "'金卡' AS member_level" in sql
        assert "FROM shop_dm.dwd_customer" in sql

    def test_set_from_column(self):
        update = _parse_update("UPDATE t SET a = b")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "b AS a" in sql

    def test_with_where(self):
        update = _parse_update("UPDATE t SET a = 1 WHERE id > 10")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "WHERE" in sql or "id > 10" in sql

    def test_with_join(self):
        update = _parse_update("UPDATE t JOIN s ON t.id = s.id SET t.a = s.b")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "JOIN" in sql
        assert "ON" in sql

    def test_case_when_set(self):
        update = _parse_update("""
            UPDATE t SET col = CASE WHEN x > 0 THEN 1 ELSE col END
        """)
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "CASE" in sql
        assert "col" in sql

    def test_multiple_sets(self):
        update = _parse_update("UPDATE t SET a = 1, b = 2, c = a + b WHERE flag = 1")
        select = update_to_select(update)
        sql = select.sql(dialect="doris")
        assert "1 AS a" in sql
        assert "2 AS b" in sql
        assert "a + b AS c" in sql
        assert "flag = 1" in sql

    def test_output_is_select(self):
        update = _parse_update("UPDATE t SET a = 1")
        select = update_to_select(update)
        assert isinstance(select, exp.Select)

    def test_no_where(self):
        update = _parse_update("UPDATE t SET a = 1")
        select = update_to_select(update)
        assert select.args.get("where") is None
