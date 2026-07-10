"""DDL 自动推导功能测试: 覆盖 5 类场景。"""

import copy

import pytest

from dw_refactor_agent.ddl_deriver.ddl_deriver import (
    AlterTable,
    ColumnDef,
    CreateTable,
    DropTable,
    RenameTable,
    TableDef,
    changes_to_json,
    derive_ddl_changes,
    extract_table_id,
    format_changes,
    generate_table_id,
    inject_table_id,
    load_tables_from_dir,
    parse_create_table,
)

# ============================================================
# 测试数据
# ============================================================

BASE_TABLES = {
    "ods_customer": TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("customer_name", "VARCHAR(64)", nullable=False),
            ColumnDef("gender", "VARCHAR(4)", nullable=True),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
        raw_ddl="",
    ),
    "ods_order": TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("total_amount", "DECIMAL(12,2)", nullable=False),
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
        raw_ddl="",
    ),
}


def _base_table(name):
    return copy.deepcopy(BASE_TABLES[name])


DEMO_DDL = {
    "ods_customer": """\
DROP TABLE IF EXISTS shop_dm.ods_customer;
CREATE TABLE IF NOT EXISTS shop_dm.ods_customer (
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    customer_name VARCHAR(64) NOT NULL COMMENT '客户姓名',
    phone VARCHAR(20) NULL COMMENT '手机号'
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
""",
    "ods_order": """\
DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id BIGINT NOT NULL COMMENT '订单ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    total_amount DECIMAL(12,2) NOT NULL COMMENT '订单总额'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
""",
    "dwd_order_detail": """\
DROP TABLE IF EXISTS shop_dm.dwd_order_detail;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_order_detail (
    order_item_id BIGINT NOT NULL COMMENT '订单明细ID',
    order_id BIGINT NOT NULL COMMENT '订单ID',
    subtotal DECIMAL(12,2) NOT NULL COMMENT '小计金额'
) ENGINE=OLAP
UNIQUE KEY(order_item_id)
DISTRIBUTED BY HASH(order_item_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
""",
}


def _write_demo_ddl_files(ddl_dir):
    ddl_dir.mkdir()
    for table_name, ddl in DEMO_DDL.items():
        (ddl_dir / f"{table_name}.sql").write_text(ddl, encoding="utf-8")


def test_table_lifecycle_derivation_scenarios():
    _assert_create_table()
    _assert_drop_table()
    _assert_rename_table()
    _assert_rename_prefers_high_similarity()
    _assert_rename_too_different_falls_back_to_drop_create()
    _assert_batch_create_drop()
    _assert_no_changes()
    _assert_create_table_does_not_generate_uuid()


def test_rename_with_followup_change_scenarios():
    _assert_rename_add_column()
    _assert_rename_drop_column()
    _assert_rename_modify_column()
    _assert_rename_table_with_rename_column()
    _assert_rename_and_alter_same_table()
    _assert_rename_by_uuid()
    _assert_rename_by_uuid_with_alter()
    _assert_rename_by_uuid_takes_precedence()
    _assert_different_uuid_low_jaccard_not_rename()


def test_alter_table_derivation_scenarios():
    _assert_alter_add_column()
    _assert_alter_drop_column()
    _assert_alter_modify_column()
    _assert_alter_modify_default()
    _assert_alter_modify_comment()
    _assert_alter_default_and_comment_and_type()
    _assert_alter_mixed()
    _assert_alter_rename_column()
    _assert_alter_rename_prefers_matching_column_comments()
    _assert_alter_rename_and_add_column()
    _assert_alter_rename_no_false_positive()
    _assert_alter_rename_skips_ambiguous_same_type_columns_without_semantics()
    _assert_alter_case_only_rename_uses_temporary_column()
    _assert_alter_case_only_rename_avoids_temporary_column_collision()


def test_change_formatting_and_table_id_scenarios():
    _assert_alter_rename_output_json()
    _assert_format_changes()
    _assert_changes_to_json()
    _assert_both_empty()
    _assert_extract_table_id()
    _assert_inject_table_id()
    _assert_generate_table_id_format()


# ============================================================
# 1. 新增表 (CREATE TABLE)
# ============================================================


def _assert_create_table():
    old = {}
    new = {
        "ods_customer": _base_table("ods_customer"),
    }
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], CreateTable)
    assert changes[0].table_def.short_name == "ods_customer"


# ============================================================
# 2. 删除表 (DROP TABLE)
# ============================================================


def _assert_drop_table():
    old = {
        "ods_customer": _base_table("ods_customer"),
    }
    new = {}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], DropTable)
    assert changes[0].table_name == "shop_dm.ods_customer"


# ============================================================
# 3. 表重命名 (RENAME TABLE)
# ============================================================


def _assert_rename_table():
    renamed = TableDef(
        full_name="shop_dm.ods_customer_v2",
        short_name="ods_customer_v2",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("customer_name", "VARCHAR(64)", nullable=False),
            ColumnDef("gender", "VARCHAR(4)", nullable=True),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
        raw_ddl="",
    )
    old = {"ods_customer": _base_table("ods_customer")}
    new = {"ods_customer_v2": renamed}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], RenameTable)
    assert changes[0].old_name == "shop_dm.ods_customer"
    assert changes[0].new_name == "shop_dm.ods_customer_v2"


def _assert_rename_prefers_high_similarity():
    """重命名检测: 结构差异大的不应匹配为 RENAME."""
    very_different = TableDef(
        full_name="shop_dm.ods_other",
        short_name="ods_other",
        columns=[ColumnDef("id", "BIGINT", nullable=False)],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        raw_ddl="",
    )
    old = {"ods_customer": _base_table("ods_customer")}
    new = {"ods_other": very_different}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 2
    assert any(isinstance(c, DropTable) for c in changes)
    assert any(isinstance(c, CreateTable) for c in changes)
    assert not any(isinstance(c, RenameTable) for c in changes)


def _assert_rename_add_column():
    """RENAME + ADD COLUMN: 旧表重命名并新增列."""
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
            ColumnDef(
                "address", "VARCHAR(256)", nullable=True, comment="地址"
            ),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer": new_t}
    )
    assert len(changes) == 2
    assert isinstance(changes[0], RenameTable)
    assert changes[0].old_name == "shop_dm.ods_user_info"
    assert changes[0].new_name == "shop_dm.ods_customer"
    assert isinstance(changes[1], AlterTable)
    assert changes[1].table_name == "shop_dm.ods_customer"
    assert len(changes[1].adds) == 1
    assert changes[1].adds[0].name == "address"


def _assert_rename_drop_column():
    """RENAME + DROP COLUMN."""
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
            ColumnDef("status", "VARCHAR(8)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer": new_t}
    )
    assert len(changes) == 2
    assert isinstance(changes[0], RenameTable)
    assert isinstance(changes[1], AlterTable)
    assert changes[1].table_name == "shop_dm.ods_customer"
    assert len(changes[1].drops) == 1
    assert changes[1].drops[0].name == "status"


def _assert_rename_modify_column():
    """RENAME + MODIFY COLUMN: 当仅改类型的签名相似度低于阈值,退化 DROP+CREATE."""
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(128)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(32)", nullable=True, comment="手机号"),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    # 类型变化导致签名不匹配,相似度仅 2/6=0.33,退化 DROP+CREATE
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer": new_t}
    )
    assert len(changes) == 2
    assert not any(isinstance(c, RenameTable) for c in changes)
    assert any(isinstance(c, DropTable) for c in changes)
    assert any(isinstance(c, CreateTable) for c in changes)


def _assert_rename_too_different_falls_back_to_drop_create():
    """大规模结构变更,退化 DROP + CREATE 而非 RENAME."""
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
            ColumnDef("status", "VARCHAR(8)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(128)", nullable=False, comment="全名"),
            ColumnDef("phone", "VARCHAR(32)", nullable=True),
            ColumnDef("email", "VARCHAR(128)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer": new_t}
    )
    assert len(changes) == 2
    assert any(isinstance(c, DropTable) for c in changes)
    assert any(isinstance(c, CreateTable) for c in changes)
    assert not any(isinstance(c, RenameTable) for c in changes)


# ============================================================
# 4. 修改表结构 (ALTER TABLE)
# ============================================================


def _assert_alter_add_column():
    old = {"ods_customer": _base_table("ods_customer")}
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("customer_name", "VARCHAR(64)", nullable=False),
            ColumnDef("gender", "VARCHAR(4)", nullable=True),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
            ColumnDef("email", "VARCHAR(128)", nullable=True, comment="邮箱"),
        ],
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
        raw_ddl="",
    )
    new = {"ods_customer": new_t}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].adds) == 1
    assert changes[0].adds[0].name == "email"
    assert len(changes[0].drops) == 0
    assert len(changes[0].modifies) == 0


def _assert_alter_drop_column():
    old = {"ods_customer": _base_table("ods_customer")}
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("customer_name", "VARCHAR(64)", nullable=False),
            ColumnDef("gender", "VARCHAR(4)", nullable=True),
            ColumnDef("age", "INT", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
        raw_ddl="",
    )
    new = {"ods_customer": new_t}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].drops) == 1
    assert changes[0].drops[0].name == "phone"
    assert len(changes[0].adds) == 0


def _assert_alter_modify_column():
    old = {"ods_customer": _base_table("ods_customer")}
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef(
                "customer_name", "VARCHAR(128)", nullable=False
            ),  # 64→128
            ColumnDef("gender", "VARCHAR(4)", nullable=True),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
        raw_ddl="",
    )
    new = {"ods_customer": new_t}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].modifies) == 1
    assert changes[0].modifies[0][0].name == "customer_name"
    assert changes[0].modifies[0][1].data_type == "VARCHAR(128)"


def _assert_alter_modify_default():
    """ALTER TABLE: 仅修改列的默认值."""
    old_t = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("status", "VARCHAR(8)", nullable=False, default="NEW"),
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("status", "VARCHAR(8)", nullable=False, default="DONE"),
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    changes = derive_ddl_changes({"ods_order": old_t}, {"ods_order": new_t})
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].modifies) == 1
    assert changes[0].modifies[0][0].name == "status"


def _assert_alter_modify_comment():
    """ALTER TABLE: 仅修改列注释."""
    old_t = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False, comment="订单ID")
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False, comment="订单主键")
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    changes = derive_ddl_changes({"ods_order": old_t}, {"ods_order": new_t})
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].modifies) == 1
    assert changes[0].modifies[0][0].name == "order_id"


def _assert_alter_default_and_comment_and_type():
    """ALTER TABLE: 同时修改默认值+注释+类型."""
    old_t = TableDef(
        full_name="shop_dm.ods_product",
        short_name="ods_product",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef(
                "price",
                "DECIMAL(10,2)",
                nullable=False,
                default="0.00",
                comment="原价",
            ),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    new_t = TableDef(
        full_name="shop_dm.ods_product",
        short_name="ods_product",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef(
                "price",
                "DECIMAL(12,2)",
                nullable=True,
                default="9.99",
                comment="售价",
            ),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
    )
    changes = derive_ddl_changes(
        {"ods_product": old_t}, {"ods_product": new_t}
    )
    assert len(changes) == 1
    assert isinstance(changes[0], AlterTable)
    assert len(changes[0].modifies) == 1
    assert changes[0].modifies[0][0].name == "price"
    sql = changes[0].to_sql()
    assert "DECIMAL(12,2)" in sql
    assert "NULL" in sql
    assert "9.99" in sql
    assert "售价" in sql


def _assert_batch_create_drop():
    """批量: 同时 3 表新增 + 2 表删除 + 1 表修改,互不干扰."""
    # 各表用不同列名避免 rename 误匹配
    old_tables = {
        "a_old": TableDef(
            full_name="shop_dm.a_old",
            short_name="a_old",
            columns=[ColumnDef("a_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["a_id"],
            distribution_col="a_id",
        ),
        "b_old": TableDef(
            full_name="shop_dm.b_old",
            short_name="b_old",
            columns=[ColumnDef("b_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["b_id"],
            distribution_col="b_id",
        ),
        "c": TableDef(
            full_name="shop_dm.c",
            short_name="c",
            columns=[ColumnDef("c_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["c_id"],
            distribution_col="c_id",
        ),
        "keep": TableDef(
            full_name="shop_dm.keep",
            short_name="keep",
            columns=[ColumnDef("id", "BIGINT"), ColumnDef("x", "INT")],
            key_type="DUPLICATE",
            key_columns=["id"],
            distribution_col="id",
        ),
    }
    new_tables = {
        "c": TableDef(
            full_name="shop_dm.c",
            short_name="c",
            columns=[ColumnDef("c_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["c_id"],
            distribution_col="c_id",
        ),
        "keep": TableDef(
            full_name="shop_dm.keep",
            short_name="keep",
            columns=[ColumnDef("id", "BIGINT"), ColumnDef("x", "VARCHAR(32)")],
            key_type="DUPLICATE",
            key_columns=["id"],
            distribution_col="id",
        ),
        "d_new": TableDef(
            full_name="shop_dm.d_new",
            short_name="d_new",
            columns=[ColumnDef("d_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["d_id"],
            distribution_col="d_id",
        ),
        "e_new": TableDef(
            full_name="shop_dm.e_new",
            short_name="e_new",
            columns=[ColumnDef("e_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["e_id"],
            distribution_col="e_id",
        ),
        "f_new": TableDef(
            full_name="shop_dm.f_new",
            short_name="f_new",
            columns=[ColumnDef("f_id", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["f_id"],
            distribution_col="f_id",
        ),
    }
    changes = derive_ddl_changes(old_tables, new_tables)
    types = {c.change_type for c in changes}
    assert types == {"CREATE", "DROP", "ALTER"}
    assert sum(1 for c in changes if c.change_type == "CREATE") == 3
    assert sum(1 for c in changes if c.change_type == "DROP") == 2
    assert sum(1 for c in changes if c.change_type == "ALTER") == 1


def _assert_alter_mixed():
    """增/删/改列同时发生."""
    old_t = TableDef(
        full_name="shop_dm.dwd_customer",
        short_name="dwd_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
            ColumnDef("status", "VARCHAR(8)", nullable=True),
        ],
        key_type="UNIQUE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_customer",
        short_name="dwd_customer",
        columns=[
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef("full_name", "VARCHAR(128)", nullable=False),  # renamed
            ColumnDef("age", "INT", nullable=True),
            ColumnDef(
                "phone", "VARCHAR(32)", nullable=False, comment="手机号"
            ),  # type+nullable
            ColumnDef("email", "VARCHAR(128)", nullable=True),  # new
        ],
        key_type="UNIQUE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
    )
    old, new = {"dwd_customer": old_t}, {"dwd_customer": new_t}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    assert {c.name for c in a.drops} == {"name", "status"}
    assert {c.name for c in a.adds} == {"full_name", "email"}
    assert {old.name for old, new in a.modifies} == {"phone"}


def _assert_alter_rename_column():
    """ALTER TABLE: 列重命名 (data_type+nullable 相同 → RENAME COLUMN)."""
    old_t = TableDef(
        full_name="shop_dm.dwd_order_detail",
        short_name="dwd_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef(
                "unit_price", "DECIMAL(12,2)", nullable=False, comment="单价"
            ),
            ColumnDef("quantity", "INT", nullable=False),
        ],
        key_type="UNIQUE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order_detail",
        short_name="dwd_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef(
                "price_unit", "DECIMAL(12,2)", nullable=False, comment="单价"
            ),
            ColumnDef("quantity", "INT", nullable=False),
        ],
        key_type="UNIQUE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    changes = derive_ddl_changes(
        {"dwd_order_detail": old_t}, {"dwd_order_detail": new_t}
    )
    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    assert len(a.renames) == 1
    assert a.renames[0] == ("unit_price", "price_unit")
    assert len(a.drops) == 0
    assert len(a.adds) == 0
    assert len(a.modifies) == 0
    sql = a.to_sql()
    assert "RENAME COLUMN unit_price price_unit" in sql
    assert "__tmp_" not in sql


def _assert_alter_rename_prefers_matching_column_comments():
    """列同类型时, 应优先按注释语义匹配, 避免指标字段互换."""
    tid = generate_table_id()
    old_t = TableDef(
        full_name="shop_dm.dws_product_sales_daily",
        short_name="dws_product_sales_daily",
        columns=[
            ColumnDef(
                "order_count",
                "INT",
                nullable=False,
                default="0",
                comment="订单笔数",
            ),
            ColumnDef(
                "sale_quantity",
                "INT",
                nullable=False,
                default="0",
                comment="销售数量",
            ),
        ],
        key_type="UNIQUE",
        key_columns=["order_count"],
        distribution_col="order_count",
        table_id=tid,
    )
    new_t = TableDef(
        full_name="shop_dm.I_SHOP_PROD_SALES_DS",
        short_name="I_SHOP_PROD_SALES_DS",
        columns=[
            ColumnDef(
                "ORDER_CNT",
                "INT",
                nullable=False,
                default="0",
                comment="订单笔数",
            ),
            ColumnDef(
                "D_PROD_SALE_QTY",
                "INT",
                nullable=False,
                default="0",
                comment="销售数量",
            ),
        ],
        key_type="UNIQUE",
        key_columns=["ORDER_CNT"],
        distribution_col="ORDER_CNT",
        table_id=tid,
    )

    changes = derive_ddl_changes(
        {"dws_product_sales_daily": old_t},
        {"I_SHOP_PROD_SALES_DS": new_t},
    )

    a = next(c for c in changes if isinstance(c, AlterTable))
    assert a.renames == [
        ("order_count", "ORDER_CNT"),
        ("sale_quantity", "D_PROD_SALE_QTY"),
    ]
    sql = a.to_sql()
    assert sql.count("ALTER TABLE shop_dm.I_SHOP_PROD_SALES_DS") == 2
    assert "RENAME COLUMN order_count ORDER_CNT;" in sql
    assert "RENAME COLUMN sale_quantity D_PROD_SALE_QTY;" in sql
    assert "RENAME COLUMN order_count ORDER_CNT," not in sql


def _assert_alter_rename_and_add_column():
    """ALTER TABLE: 列重命名 + 新增另一列."""
    old_t = TableDef(
        full_name="shop_dm.dwd_order_detail",
        short_name="dwd_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef(
                "unit_price", "DECIMAL(12,2)", nullable=False, comment="单价"
            ),
        ],
        key_type="UNIQUE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order_detail",
        short_name="dwd_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef(
                "price_unit", "DECIMAL(12,2)", nullable=False, comment="单价"
            ),
            ColumnDef(
                "discount", "DECIMAL(12,2)", nullable=True, comment="折扣"
            ),
        ],
        key_type="UNIQUE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    changes = derive_ddl_changes(
        {"dwd_order_detail": old_t}, {"dwd_order_detail": new_t}
    )
    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    assert a.renames == [("unit_price", "price_unit")]
    assert len(a.adds) == 1
    assert a.adds[0].name == "discount"
    assert len(a.drops) == 0
    sql = a.to_sql()
    assert "RENAME COLUMN unit_price price_unit" in sql
    assert "ADD COLUMN discount" in sql


def _assert_alter_case_only_rename_uses_temporary_column():
    """大小写-only 列重命名应拆成 Doris 可执行的两步."""
    old_t = TableDef(
        full_name="shop_dm.t1",
        short_name="t1",
        columns=[
            ColumnDef("store_id", "BIGINT"),
            ColumnDef("amount", "DECIMAL(10,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["store_id"],
        distribution_col="store_id",
    )
    new_t = TableDef(
        full_name="shop_dm.t1",
        short_name="t1",
        columns=[
            ColumnDef("STORE_ID", "BIGINT"),
            ColumnDef("amount", "DECIMAL(10,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["STORE_ID"],
        distribution_col="STORE_ID",
    )

    changes = derive_ddl_changes({"t1": old_t}, {"t1": new_t})

    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    assert a.renames == [("store_id", "STORE_ID")]
    sql = a.to_sql()
    assert "RENAME COLUMN store_id STORE_ID" not in sql
    assert "RENAME COLUMN store_id __tmp_STORE_ID;" in sql
    assert "RENAME COLUMN __tmp_STORE_ID STORE_ID;" in sql

    result = changes_to_json(changes)
    entry = result["changes"][0]
    assert entry["renames"] == [{"old": "store_id", "new": "STORE_ID"}]
    assert entry["case_only_renames"] == [
        {
            "old": "store_id",
            "new": "STORE_ID",
            "temporary": "__tmp_STORE_ID",
            "steps": [
                {"old": "store_id", "new": "__tmp_STORE_ID"},
                {"old": "__tmp_STORE_ID", "new": "STORE_ID"},
            ],
        }
    ]


def _assert_alter_case_only_rename_avoids_temporary_column_collision():
    """临时列名与现有列冲突时应继续追加后缀."""
    old_t = TableDef(
        full_name="shop_dm.t1",
        short_name="t1",
        columns=[
            ColumnDef("store_id", "BIGINT"),
            ColumnDef("__tmp_STORE_ID", "VARCHAR(32)"),
            ColumnDef("amount", "DECIMAL(10,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["store_id"],
        distribution_col="store_id",
    )
    new_t = TableDef(
        full_name="shop_dm.t1",
        short_name="t1",
        columns=[
            ColumnDef("STORE_ID", "BIGINT"),
            ColumnDef("__tmp_STORE_ID", "VARCHAR(32)"),
            ColumnDef("amount", "DECIMAL(10,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["STORE_ID"],
        distribution_col="STORE_ID",
    )

    changes = derive_ddl_changes({"t1": old_t}, {"t1": new_t})

    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    sql = a.to_sql()
    assert "RENAME COLUMN store_id __tmp_STORE_ID;" not in sql
    assert "RENAME COLUMN store_id __tmp_STORE_ID_1;" in sql
    assert "RENAME COLUMN __tmp_STORE_ID_1 STORE_ID;" in sql
    entry = changes_to_json(changes)["changes"][0]
    assert entry["case_only_renames"][0]["temporary"] == "__tmp_STORE_ID_1"


def _assert_alter_rename_no_false_positive():
    """不同类型/可空性的 drop+add 不应误判为重命名."""
    old_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("old_col", "VARCHAR(64)", nullable=False),
            ColumnDef("keep", "INT", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["old_col"],
        distribution_col="old_col",
    )
    new_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("new_col", "BIGINT", nullable=True),  # 类型+可空性都不同
            ColumnDef("keep", "INT", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["new_col"],
        distribution_col="new_col",
    )
    changes = derive_ddl_changes({"test": old_t}, {"test": new_t})
    assert len(changes) == 1
    a = changes[0]
    assert isinstance(a, AlterTable)
    assert len(a.renames) == 0
    assert len(a.drops) == 1
    assert a.drops[0].name == "old_col"
    assert len(a.adds) == 1
    assert a.adds[0].name == "new_col"


def _assert_alter_rename_skips_ambiguous_same_type_columns_without_semantics():
    """多个同类型字段缺少语义证据时, 不应任意推断 rename."""
    old_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("old_a", "INT", nullable=False),
            ColumnDef("old_b", "INT", nullable=False),
        ],
        key_type="DUPLICATE",
        key_columns=["old_a"],
        distribution_col="old_a",
    )
    new_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("new_x", "INT", nullable=False),
            ColumnDef("new_y", "INT", nullable=False),
        ],
        key_type="DUPLICATE",
        key_columns=["new_x"],
        distribution_col="new_x",
    )

    changes = derive_ddl_changes({"test": old_t}, {"test": new_t})

    a = next(c for c in changes if isinstance(c, AlterTable))
    assert a.renames == []
    assert {col.name for col in a.drops} == {"old_a", "old_b"}
    assert {col.name for col in a.adds} == {"new_x", "new_y"}


def _assert_rename_table_with_rename_column():
    """RENAME TABLE + 列重命名同时发生 (通过 UUID 绑定)."""
    tid = generate_table_id()
    old_t = TableDef(
        full_name="shop_dm.ods_order_detail",
        short_name="ods_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("unit_price", "DECIMAL(12,2)", nullable=False),
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
        table_id=tid,
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order_detail",
        short_name="dwd_order_detail",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("price_unit", "DECIMAL(12,2)", nullable=False),
        ],
        key_type="UNIQUE",
        key_columns=["order_id"],
        distribution_col="order_id",
        table_id=tid,
    )
    changes = derive_ddl_changes(
        {"ods_order_detail": old_t}, {"dwd_order_detail": new_t}
    )
    assert len(changes) == 2
    assert isinstance(changes[0], RenameTable)
    assert isinstance(changes[1], AlterTable)
    a = changes[1]
    assert a.renames == [("unit_price", "price_unit")]
    assert len(a.adds) == 0
    assert len(a.drops) == 0


def _assert_alter_rename_output_json():
    """列重命名在 JSON 输出中的格式."""
    old_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("unit_price", "INT"),
            ColumnDef("b", "VARCHAR(16)"),
        ],
        key_type="DUPLICATE",
        key_columns=["unit_price"],
        distribution_col="unit_price",
    )
    new_t = TableDef(
        full_name="shop_dm.test",
        short_name="test",
        columns=[
            ColumnDef("price_unit", "INT"),
            ColumnDef("b", "VARCHAR(16)"),
        ],
        key_type="DUPLICATE",
        key_columns=["price_unit"],
        distribution_col="price_unit",
    )
    changes = derive_ddl_changes({"test": old_t}, {"test": new_t})
    result = changes_to_json(changes)
    entry = result["changes"][0]
    assert entry["change_type"] == "ALTER"
    assert entry["renames"] == [{"old": "unit_price", "new": "price_unit"}]
    # 确认未出现在 adds/drops 中
    assert not any(c["name"] == "unit_price" for c in entry["drops"])
    assert not any(c["name"] == "price_unit" for c in entry["adds"])


def test_column_id_matches_rename_with_followup_modify():
    table_id = "91ed8f6a-736d-4896-888e-f9225741b7fa"
    key_column_id = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
    metric_column_id = "77eb791d-9856-4cc2-a77c-89f46ee626b2"
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef(
                "order_id",
                "BIGINT",
                nullable=False,
                column_id=key_column_id,
            ),
            ColumnDef(
                "unit_price",
                "DECIMAL(12,2)",
                nullable=False,
                default="0",
                comment="单价",
                column_id=metric_column_id,
            ),
        ],
        key_columns=["order_id"],
        distribution_col="order_id",
        table_id=table_id,
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef(
                "order_id",
                "BIGINT",
                nullable=False,
                column_id=key_column_id,
            ),
            ColumnDef(
                "price_unit",
                "DECIMAL(14,2)",
                nullable=True,
                default="1",
                comment="成交单价",
                column_id=metric_column_id,
            ),
        ],
        key_columns=["order_id"],
        distribution_col="order_id",
        table_id=table_id,
    )

    changes = derive_ddl_changes(
        {"dwd_order": old_t},
        {"dwd_order": new_t},
        legacy_identity=False,
    )

    change = changes[0]
    assert isinstance(change, AlterTable)
    assert change.renames == [("unit_price", "price_unit")]
    assert [(old.name, new.name) for old, new in change.modifies] == [
        ("unit_price", "price_unit")
    ]
    sql = change.to_sql()
    assert sql.index("RENAME COLUMN unit_price price_unit") < sql.index(
        "MODIFY COLUMN price_unit DECIMAL(14,2) NULL DEFAULT 1"
    )
    rename = changes_to_json(changes)["changes"][0]["renames"][0]
    assert rename == {
        "old": "unit_price",
        "new": "price_unit",
        "column_id": metric_column_id,
        "matched_by": "column_id",
    }


def test_different_column_ids_are_drop_add_in_strict_mode():
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef(
                "old_metric",
                "INT",
                nullable=False,
                comment="指标",
                column_id="6bfa89c0-1e30-4f92-a25e-b5a39ab94880",
            )
        ],
        table_id="91ed8f6a-736d-4896-888e-f9225741b7fa",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef(
                "new_metric",
                "INT",
                nullable=False,
                comment="指标",
                column_id="77eb791d-9856-4cc2-a77c-89f46ee626b2",
            )
        ],
        table_id="91ed8f6a-736d-4896-888e-f9225741b7fa",
    )

    change = derive_ddl_changes(
        {"dwd_order": old_t},
        {"dwd_order": new_t},
        legacy_identity=False,
    )[0]

    assert isinstance(change, AlterTable)
    assert change.renames == []
    assert [column.name for column in change.drops] == ["old_metric"]
    assert [column.name for column in change.adds] == ["new_metric"]


def test_different_table_ids_replace_same_named_table_in_strict_mode():
    column_id = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("order_id", "BIGINT", column_id=column_id)],
        table_id="91ed8f6a-736d-4896-888e-f9225741b7fa",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("order_id", "BIGINT", column_id=column_id)],
        table_id="1db7309f-1f9e-4393-807c-7d836ea25727",
    )

    changes = derive_ddl_changes(
        {"dwd_order": old_t},
        {"dwd_order": new_t},
        legacy_identity=False,
    )

    assert [type(change) for change in changes] == [DropTable, CreateTable]


def test_different_table_ids_disable_similarity_rename():
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("order_id", "BIGINT")],
        table_id="91ed8f6a-736d-4896-888e-f9225741b7fa",
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order_v2",
        short_name="dwd_order_v2",
        columns=[ColumnDef("order_id", "BIGINT")],
        table_id="1db7309f-1f9e-4393-807c-7d836ea25727",
    )

    changes = derive_ddl_changes({"dwd_order": old_t}, {"dwd_order_v2": new_t})

    assert not any(isinstance(change, RenameTable) for change in changes)
    assert [type(change) for change in changes] == [DropTable, CreateTable]


def test_legacy_column_rename_requires_positive_evidence():
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("legacy_flag", "INT", nullable=False)],
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("new_metric", "INT", nullable=False)],
    )

    change = derive_ddl_changes({"dwd_order": old_t}, {"dwd_order": new_t})[0]

    assert isinstance(change, AlterTable)
    assert change.renames == []
    assert [column.name for column in change.drops] == ["legacy_flag"]
    assert [column.name for column in change.adds] == ["new_metric"]


def test_legacy_column_rename_rejects_weak_token_overlap():
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("customer_amount_total", "INT")],
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[ColumnDef("customer_status_flag", "INT")],
    )

    change = derive_ddl_changes({"dwd_order": old_t}, {"dwd_order": new_t})[0]

    assert isinstance(change, AlterTable)
    assert change.renames == []


def test_legacy_duplicate_comments_do_not_disambiguate_renames():
    old_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef("old_a", "INT", comment="指标"),
            ColumnDef("old_b", "INT", comment="指标"),
        ],
    )
    new_t = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        columns=[
            ColumnDef("new_x", "INT", comment="指标"),
            ColumnDef("new_y", "INT", comment="指标"),
        ],
    )

    change = derive_ddl_changes({"dwd_order": old_t}, {"dwd_order": new_t})[0]

    assert isinstance(change, AlterTable)
    assert change.renames == []


# ============================================================
# 5. 无变更
# ============================================================


def _assert_no_changes():
    old = {"ods_customer": _base_table("ods_customer")}
    new = {"ods_customer": _base_table("ods_customer")}
    changes = derive_ddl_changes(old, new)
    assert len(changes) == 0


# ============================================================
# 6. 集成测试: 从真实 DDL 文件加载并推导
# ============================================================


def test_from_fixture_ddl_single_change(tmp_path):
    """DDL 文件: 重命名 ods_customer → ods_customer_v2."""
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()

    content = DEMO_DDL["ods_customer"]
    (old_dir / "ods_customer.sql").write_text(content)

    new_content = content.replace("ods_customer", "ods_customer_v2")
    (new_dir / "ods_customer_v2.sql").write_text(new_content)

    old_tables = load_tables_from_dir(old_dir)
    new_tables = load_tables_from_dir(new_dir)
    changes = derive_ddl_changes(old_tables, new_tables)

    assert len(changes) >= 1
    renames = [c for c in changes if isinstance(c, RenameTable)]
    assert len(renames) == 1
    assert "ods_customer" in renames[0].old_name
    assert "ods_customer_v2" in renames[0].new_name


# ============================================================
# 7. 输出格式测试
# ============================================================


def _assert_format_changes():
    old = {"t": _base_table("ods_customer")}
    new = {}
    changes = derive_ddl_changes(old, new)
    sql = format_changes(changes)
    assert "DROP TABLE" in sql
    assert "shop_dm.ods_customer" in sql


def _assert_changes_to_json():
    old = {"t": _base_table("ods_customer")}
    new = {}
    changes = derive_ddl_changes(old, new)
    result = changes_to_json(changes)
    assert "changes" in result
    assert result["changes"][0]["change_type"] == "DROP"
    assert "sql" in result["changes"][0]


# ============================================================
# 8. 边界情况
# ============================================================


def _assert_both_empty():
    assert derive_ddl_changes({}, {}) == []


def _assert_rename_and_alter_same_table():
    """同名表修改 + 其他表重命名同时发生."""
    old = {
        "ods_customer": _base_table("ods_customer"),
        "ods_order": _base_table("ods_order"),
    }
    base_customer = _base_table("ods_customer")
    new_customer = TableDef(
        full_name="shop_dm.ods_customer_v2",
        short_name="ods_customer_v2",
        columns=base_customer.columns.copy(),
        key_type="DUPLICATE",
        key_columns=["customer_id"],
        distribution_col="customer_id",
    )
    new_order = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("order_id", "BIGINT", nullable=False),
            ColumnDef("customer_id", "BIGINT", nullable=False),
            ColumnDef(
                "total_amount", "DECIMAL(14,2)", nullable=False
            ),  # type changed
            ColumnDef(
                "discount", "DECIMAL(12,2)", nullable=True
            ),  # new column
        ],
        key_type="DUPLICATE",
        key_columns=["order_id"],
        distribution_col="order_id",
    )
    new = {"ods_customer_v2": new_customer, "ods_order": new_order}
    changes = derive_ddl_changes(old, new)

    types = {c.change_type for c in changes}
    assert "RENAME" in types
    assert "ALTER" in types

    renames = [c for c in changes if isinstance(c, RenameTable)]
    alters = [c for c in changes if isinstance(c, AlterTable)]
    assert len(renames) == 1
    assert len(alters) == 1
    assert alters[0].table_name == "shop_dm.ods_order"
    assert {c.name for c in alters[0].adds} == {"discount"}
    assert {c.name for c in alters[0].drops} == set()
    assert {o.name for o, n in alters[0].modifies} == {"total_amount"}


def test_parse_fixture_ddl_files(tmp_path):
    """验证 DDL 文件能被正确解析."""
    ddl_dir = tmp_path / "ddl"
    _write_demo_ddl_files(ddl_dir)

    for f in sorted(ddl_dir.glob("*.sql")):
        content = f.read_text(encoding="utf-8")
        t = parse_create_table(content)
        assert t is not None, f"Failed to parse {f.name}"
        assert t.short_name == f.stem
        assert len(t.columns) >= 1


def test_parse_create_table_reads_column_ids():
    first_id = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
    second_id = "77eb791d-9856-4cc2-a77c-89f46ee626b2"
    ddl = f"""\
-- table_id: 91ed8f6a-736d-4896-888e-f9225741b7fa
CREATE TABLE shop_dm.dwd_order_detail (
    -- column_id: {first_id}
    order_id BIGINT NOT NULL COMMENT '订单ID',
    -- column_id: {second_id}
    amount DECIMAL(12,2) NOT NULL COMMENT '金额'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10;
"""

    table = parse_create_table(ddl)

    assert table is not None
    assert [column.column_id for column in table.columns] == [
        first_id,
        second_id,
    ]


def test_schema_ids_match_case_insensitively_in_strict_mode():
    table_id = "91ed8f6a-736d-4896-888e-f9225741b7fa"
    column_id = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
    old = TableDef(
        full_name="shop_dm.dwd_order",
        short_name="dwd_order",
        table_id=table_id,
        columns=[
            ColumnDef(
                "unit_price",
                "DECIMAL(12,2)",
                nullable=False,
                column_id=column_id,
            )
        ],
    )
    new = TableDef(
        full_name="shop_dm.dwd_order_v2",
        short_name="dwd_order_v2",
        table_id=table_id.upper(),
        columns=[
            ColumnDef(
                "price_unit",
                "DECIMAL(12,2)",
                nullable=False,
                column_id=column_id.upper(),
            )
        ],
    )

    changes = derive_ddl_changes(
        {"dwd_order": old},
        {"dwd_order_v2": new},
        legacy_identity=False,
    )

    assert [change.change_type for change in changes] == ["RENAME", "ALTER"]
    assert changes[1].renames == [("unit_price", "price_unit")]


@pytest.mark.parametrize("duplicate_side", ["old", "new"])
def test_derive_rejects_duplicate_in_memory_table_ids(duplicate_side):
    table_id = "91ed8f6a-736d-4896-888e-f9225741b7fa"
    tables = {
        "first": TableDef("demo.first", "first", table_id=table_id),
        "second": TableDef("demo.second", "second", table_id=table_id.upper()),
    }
    old_tables = tables if duplicate_side == "old" else {}
    new_tables = tables if duplicate_side == "new" else {}

    with pytest.raises(ValueError, match=f"{duplicate_side}.*table_id.*重复"):
        derive_ddl_changes(old_tables, new_tables)


@pytest.mark.parametrize("duplicate_side", ["old", "new"])
def test_derive_rejects_global_duplicate_in_memory_column_ids(duplicate_side):
    column_id = "6bfa89c0-1e30-4f92-a25e-b5a39ab94880"
    tables = {
        "first": TableDef(
            "demo.first",
            "first",
            columns=[ColumnDef("first_id", "BIGINT", column_id=column_id)],
        ),
        "second": TableDef(
            "demo.second",
            "second",
            columns=[
                ColumnDef("second_id", "BIGINT", column_id=column_id.upper())
            ],
        ),
    }
    old_tables = tables if duplicate_side == "old" else {}
    new_tables = tables if duplicate_side == "new" else {}

    with pytest.raises(ValueError, match=f"{duplicate_side}.*column_id.*重复"):
        derive_ddl_changes(old_tables, new_tables)


# ============================================================
# 9. UUID 表唯一标识测试
# ============================================================


def _assert_extract_table_id():
    assert (
        extract_table_id(
            "-- table_id: a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d\nSELECT 1"
        )
        == "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    )
    assert extract_table_id("SELECT 1") == ""


def _assert_inject_table_id():
    tid = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
    text = "-- ODS 表\nCREATE TABLE t (id INT);"
    result = inject_table_id(text, tid)
    assert f"-- table_id: {tid}" in result
    # 幂等性: 重复注入不生成双行
    result2 = inject_table_id(result, tid)
    assert result2.count("table_id") == 1


def _assert_generate_table_id_format():
    tid = generate_table_id()
    parts = tid.split("-")
    assert len(parts) == 5
    assert len(parts[0]) == 8


def _assert_rename_by_uuid():
    """相同 UUID + 不同表名 → 识别为 RENAME."""
    tid = generate_table_id()
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        table_id=tid,
    )
    new_t = TableDef(
        full_name="shop_dm.ods_customer",
        short_name="ods_customer",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        table_id=tid,
    )
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer": new_t}
    )
    assert len(changes) == 1
    assert isinstance(changes[0], RenameTable)
    assert changes[0].old_name == "shop_dm.ods_user_info"
    assert changes[0].new_name == "shop_dm.ods_customer"


def _assert_rename_by_uuid_with_alter():
    """相同 UUID + 列结构大改 → RENAME + ALTER,而非 DROP+CREATE."""
    tid = generate_table_id()
    old_t = TableDef(
        full_name="shop_dm.ods_user_info",
        short_name="ods_user_info",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("name", "VARCHAR(64)", nullable=False),
            ColumnDef("age", "INT", nullable=True),
            ColumnDef("phone", "VARCHAR(20)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        table_id=tid,
    )
    # 大幅变更: 仅 id 列相同,其余全变
    new_t = TableDef(
        full_name="shop_dm.ods_customer_profile",
        short_name="ods_customer_profile",
        columns=[
            ColumnDef("id", "BIGINT", nullable=False),
            ColumnDef("full_name", "VARCHAR(128)", nullable=False),
            ColumnDef("email", "VARCHAR(256)", nullable=True),
            ColumnDef("address", "VARCHAR(512)", nullable=True),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        table_id=tid,
    )
    changes = derive_ddl_changes(
        {"ods_user_info": old_t}, {"ods_customer_profile": new_t}
    )
    assert len(changes) == 2
    assert isinstance(changes[0], RenameTable)
    assert isinstance(changes[1], AlterTable)
    assert {c.name for c in changes[1].drops} == {"name", "age", "phone"}
    assert {c.name for c in changes[1].adds} == {
        "full_name",
        "email",
        "address",
    }


def _assert_rename_by_uuid_takes_precedence():
    """
    UUID 匹配优先于 Jaccard 相似度。
    即使另一个 rename 候选的结构相似度更高,UUID 匹配优先。
    """
    tid = generate_table_id()
    old_tables = {
        "ods_old_a": TableDef(
            full_name="shop_dm.ods_old_a",
            short_name="ods_old_a",
            columns=[
                ColumnDef("id", "BIGINT"),
                ColumnDef("val", "VARCHAR(16)"),
            ],
            key_type="DUPLICATE",
            key_columns=["id"],
            distribution_col="id",
            table_id=tid,
        ),
        "ods_old_b": TableDef(
            full_name="shop_dm.ods_old_b",
            short_name="ods_old_b",
            columns=[ColumnDef("x", "BIGINT"), ColumnDef("y", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["x"],
            distribution_col="x",
        ),
    }
    new_tables = {
        "ods_new_a": TableDef(
            full_name="shop_dm.ods_new_a",
            short_name="ods_new_a",
            columns=[
                ColumnDef("id", "BIGINT"),
                ColumnDef("val", "VARCHAR(16)"),
            ],
            key_type="DUPLICATE",
            key_columns=["id"],
            distribution_col="id",
            table_id=tid,
        ),
        # 结构完全匹配 ods_old_b,但 UUID 不存在
        "ods_new_b": TableDef(
            full_name="shop_dm.ods_new_b",
            short_name="ods_new_b",
            columns=[ColumnDef("x", "BIGINT"), ColumnDef("y", "BIGINT")],
            key_type="DUPLICATE",
            key_columns=["x"],
            distribution_col="x",
        ),
    }
    changes = derive_ddl_changes(old_tables, new_tables)
    renames = [c for c in changes if isinstance(c, RenameTable)]
    assert len(renames) == 2
    # ods_old_a → ods_new_a (UUID 匹配)
    # ods_old_b → ods_new_b (Jaccard 回退)
    rename_old_names = {r.old_short for r in renames}
    rename_new_names = {r.new_short for r in renames}
    assert rename_old_names == {"ods_old_a", "ods_old_b"}
    assert rename_new_names == {"ods_new_a", "ods_new_b"}


def _assert_different_uuid_low_jaccard_not_rename():
    """不同 UUID + 低 Jaccard 相似度 → DROP + CREATE,不视为 RENAME."""
    old_t = TableDef(
        full_name="shop_dm.ods_order",
        short_name="ods_order",
        columns=[
            ColumnDef("id", "BIGINT"),
            ColumnDef("amount", "DECIMAL(12,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        table_id=generate_table_id(),
    )
    new_t = TableDef(
        full_name="shop_dm.ods_order_v2",
        short_name="ods_order_v2",
        columns=[
            ColumnDef("order_key", "BIGINT"),
            ColumnDef("value", "DECIMAL(14,2)"),
        ],
        key_type="DUPLICATE",
        key_columns=["order_key"],
        distribution_col="order_key",
        table_id=generate_table_id(),
    )
    changes = derive_ddl_changes({"ods_order": old_t}, {"ods_order_v2": new_t})
    assert len(changes) == 2
    assert any(isinstance(c, CreateTable) for c in changes)
    assert any(isinstance(c, DropTable) for c in changes)
    assert not any(isinstance(c, RenameTable) for c in changes)


def _assert_create_table_does_not_generate_uuid():
    """DDL 推导必须保持只读, 不为新表临时生成 table_id."""
    new_t = TableDef(
        full_name="shop_dm.ods_new_table",
        short_name="ods_new_table",
        columns=[ColumnDef("id", "BIGINT", nullable=False)],
        key_type="DUPLICATE",
        key_columns=["id"],
        distribution_col="id",
        raw_ddl='CREATE TABLE shop_dm.ods_new_table (id BIGINT NOT NULL) ENGINE=OLAP DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10 PROPERTIES ("replication_num" = "1");',
    )
    changes = derive_ddl_changes({}, {"ods_new_table": new_t})
    assert len(changes) == 1
    assert isinstance(changes[0], CreateTable)
    create = changes[0]
    assert create.table_def.table_id == ""
    assert "-- table_id:" not in create.table_def.raw_ddl
