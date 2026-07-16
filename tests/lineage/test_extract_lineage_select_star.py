from tests.case_matrix import case_matrix
from tests.lineage.test_extract_lineage import (
    _direct_edges,
    build_schema_from_texts,
    extract_lineage_from_sql,
)


class TestSelectStarLineage:
    @classmethod
    def setup_class(cls):
        cls.schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_order (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.ods_customer (
                    customer_id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2),
                    etl_time DATETIME
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order_customer (
                    order_id BIGINT,
                    customer_id BIGINT,
                    amount DECIMAL(12,2),
                    customer_name VARCHAR(64)
                )
                """,
            ]
        )

    def _assert_star_expansion_failure(self, sql, file_path):
        diagnostics = []
        entries = extract_lineage_from_sql(
            sql,
            file_path,
            self.schema,
            diagnostics=diagnostics,
        )

        assert _direct_edges(entries) == set()
        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]

    def _assert_order_star_expansion(self, sql, file_path):
        diagnostics = []
        entries = extract_lineage_from_sql(
            sql,
            file_path,
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_task_alter_add_column_updates_ctas_schema_for_later_star(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE cdm.src (
                    id BIGINT
                )
                """,
            ],
            default_db="cdm",
        )
        sql = """
        CREATE TABLE cdm.tmp AS
        SELECT id FROM cdm.src;

        ALTER TABLE cdm.tmp ADD COLUMN name STRING;

        CREATE TABLE cdm.tmp_out AS
        SELECT t.* FROM cdm.tmp AS t;
        """

        entries = extract_lineage_from_sql(
            sql,
            "alter_add_column_star.sql",
            schema,
        )

        assert _direct_edges(entries) >= {
            ("cdm.src", "id", "cdm.tmp", "id"),
            ("cdm.tmp", "id", "cdm.tmp_out", "id"),
            ("cdm.tmp", "name", "cdm.tmp_out", "name"),
        }

    def test_ctas_unaliased_complex_expression_does_not_become_column_name(
        self,
    ):
        sql = """
        CREATE TABLE cdm.tmp AS
        SELECT COALESCE(
            CASE
                WHEN t1.xd_used_amt >= 40000000 THEN 40000000
                ELSE t1.xd_used_amt
            END
        )
        FROM cdm.src AS t1;

        CREATE TABLE cdm.tmp_out AS
        SELECT t.* FROM cdm.tmp AS t;
        """

        entries = extract_lineage_from_sql(sql, "ctas_expr_star.sql", {})

        assert not any(
            "COALESCE" in str(edge_part)
            for edge in _direct_edges(entries)
            for edge_part in edge
        )

    def test_subquery_star_inlines_unaliased_constant_projection(self):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.src_bill_detail (
                    bill_no STRING
                )
                """,
                """
                CREATE TABLE shop_dm.rept_bill_detail (
                    id STRING,
                    bill_no STRING,
                    data_dt DATE
                )
                """,
            ]
        )
        sql = """
        INSERT INTO shop_dm.rept_bill_detail
        SELECT
            NULL AS id,
            t.*
        FROM (
            SELECT
                bill_no,
                TO_DATE('20260602')
            FROM shop_dm.src_bill_detail
        ) t
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "a_rept_bill_dtl_d.sql",
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) >= {
            (
                "src_bill_detail",
                "bill_no",
                "rept_bill_detail",
                "bill_no",
            ),
            (None, None, "rept_bill_detail", "id"),
            (None, None, "rept_bill_detail", "data_dt"),
        }
        data_dt_entries = [
            entry
            for entry in entries
            if entry.get("target_column") == "data_dt"
        ]
        assert len(data_dt_entries) == 1
        assert data_dt_entries[0]["lineage_type"] == "direct"
        assert data_dt_entries[0]["source_type"] == "expression"
        assert data_dt_entries[0]["target_table"] == "rept_bill_detail"
        assert data_dt_entries[0]["target_column"] == "data_dt"
        assert data_dt_entries[0]["transformation_type"] == "constant"
        assert data_dt_entries[0]["source_file"] == "a_rept_bill_dtl_d.sql"
        assert "TO_DATE('20260602')" in data_dt_entries[0]["expression"]
        assert not any(
            entry.get("target_column") == "20260602" for entry in entries
        )

    @case_matrix(
        ("file_path", "sql"),
        [
            (
                "duplicate_star_join.sql",
                """
                INSERT INTO shop_dm.dwd_order_customer_flat
                SELECT *
                FROM shop_dm.ods_order_key o
                JOIN shop_dm.ods_customer_key c ON o.id = c.id
                """,
            ),
            (
                "nested_duplicate_star_join.sql",
                """
                INSERT INTO shop_dm.dwd_order_customer_flat
                SELECT *
                FROM (
                    SELECT *
                    FROM shop_dm.ods_order_key o
                    JOIN shop_dm.ods_customer_key c ON o.id = c.id
                ) t
                """,
            ),
        ],
        ids=("direct", "nested"),
    )
    def test_bare_star_join_duplicate_columns_map_by_position(
        self, file_path, sql
    ):
        schema = build_schema_from_texts(
            [
                """
                CREATE TABLE shop_dm.ods_order_key (
                    id BIGINT,
                    amount DECIMAL(12,2)
                )
                """,
                """
                CREATE TABLE shop_dm.ods_customer_key (
                    id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
                """
                CREATE TABLE shop_dm.dwd_order_customer_flat (
                    order_id BIGINT,
                    amount DECIMAL(12,2),
                    customer_id BIGINT,
                    customer_name VARCHAR(64)
                )
                """,
            ]
        )
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            file_path,
            schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            (
                "ods_order_key",
                "id",
                "dwd_order_customer_flat",
                "order_id",
            ),
            (
                "ods_order_key",
                "amount",
                "dwd_order_customer_flat",
                "amount",
            ),
            (
                "ods_customer_key",
                "id",
                "dwd_order_customer_flat",
                "customer_id",
            ),
            (
                "ods_customer_key",
                "customer_name",
                "dwd_order_customer_flat",
                "customer_name",
            ),
        }

    def test_unresolved_inner_star_does_not_leak_as_derived_column(self):
        sql = """
        INSERT INTO shop_dm.dwd_order_customer
        SELECT *
        FROM (
            SELECT *
            FROM shop_dm.missing_orders m
            JOIN shop_dm.ods_customer c ON m.customer_id = c.customer_id
        ) t
        """
        self._assert_star_expansion_failure(sql, "unresolved_inner_star.sql")

    @case_matrix(
        ("file_path", "sql"),
        [
            (
                "cte_alias_columns.sql",
                """
                INSERT INTO shop_dm.dwd_order (customer_id, amount)
                WITH renamed(customer_id, amount) AS (
                    SELECT order_id, amount
                    FROM shop_dm.ods_order
                )
                SELECT *
                FROM renamed
                """,
            ),
            (
                "subquery_alias_columns.sql",
                """
                INSERT INTO shop_dm.dwd_order (customer_id, amount)
                SELECT *
                FROM (
                    SELECT order_id, amount
                    FROM shop_dm.ods_order
                ) renamed(customer_id, amount)
                """,
            ),
        ],
        ids=("cte", "subquery"),
    )
    def test_column_alias_list_exposes_star_output_names(self, file_path, sql):
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            file_path,
            self.schema,
            diagnostics=diagnostics,
        )

        assert diagnostics == []
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_explicit_projection_from_unresolved_subquery_star_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        SELECT t.order_id
        FROM (
            SELECT *
            FROM shop_dm.missing_orders
        ) t
        """
        self._assert_star_expansion_failure(
            sql, "explicit_unresolved_subquery_star.sql"
        )

    def test_unqualified_projection_from_unresolved_subquery_star_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        SELECT order_id
        FROM (
            SELECT *
            FROM shop_dm.missing_orders
        ) t
        """
        self._assert_star_expansion_failure(
            sql, "unqualified_unresolved_subquery_star.sql"
        )

    def test_unqualified_projection_from_unresolved_cte_star_is_blocked(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id)
        WITH t AS (
            SELECT *
            FROM shop_dm.missing_orders
        )
        SELECT order_id
        FROM t
        """
        self._assert_star_expansion_failure(
            sql, "unqualified_unresolved_cte_star.sql"
        )

    def test_alias_star_with_explicit_unresolved_subquery_projection_is_blocked(
        self,
    ):
        sql = """
        INSERT INTO shop_dm.dwd_order
        SELECT o.*, missing_id AS etl_time
        FROM shop_dm.ods_order o
        JOIN (
            SELECT *
            FROM shop_dm.missing_orders
        ) t ON o.order_id = t.order_id
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "alias_star_unresolved_explicit.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) == {
            ("ods_order", "order_id", "dwd_order", "order_id"),
            ("ods_order", "customer_id", "dwd_order", "customer_id"),
            ("ods_order", "amount", "dwd_order", "amount"),
        }

    def test_union_left_unresolved_star_suppresses_later_projection(self):
        sql = """
        INSERT INTO shop_dm.dwd_order (order_id, customer_id)
        SELECT *, c.customer_name
        FROM shop_dm.missing_orders m
        JOIN shop_dm.ods_customer c ON m.customer_id = c.customer_id
        UNION ALL
        SELECT order_id, customer_id
        FROM shop_dm.ods_order
        """
        self._assert_star_expansion_failure(sql, "union_left_missing_star.sql")

    def test_ctas_known_shape_with_unresolved_source_registers_columns(self):
        sql = """
        CREATE TABLE shop_dm.tmp_order AS
        SELECT o.*, t.missing_id AS etl_time
        FROM shop_dm.ods_order o
        JOIN (
            SELECT *
            FROM shop_dm.missing_orders
        ) t ON o.order_id = t.order_id;

        INSERT INTO shop_dm.dwd_order
        SELECT *
        FROM shop_dm.tmp_order;
        """
        diagnostics = []

        entries = extract_lineage_from_sql(
            sql,
            "ctas_known_shape_unresolved_source.sql",
            self.schema,
            diagnostics=diagnostics,
        )

        assert [diagnostic["stage"] for diagnostic in diagnostics] == [
            "lineage_star_expand"
        ]
        assert _direct_edges(entries) >= {
            ("ods_order", "order_id", "tmp_order", "order_id"),
            ("ods_order", "customer_id", "tmp_order", "customer_id"),
            ("ods_order", "amount", "tmp_order", "amount"),
            ("tmp_order", "order_id", "dwd_order", "order_id"),
            ("tmp_order", "customer_id", "dwd_order", "customer_id"),
            ("tmp_order", "amount", "dwd_order", "amount"),
        }
