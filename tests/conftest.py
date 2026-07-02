from pathlib import Path

import pytest

from tests.taxonomy import TEST_TYPE_BY_FILE, TEST_TYPE_MARKERS


def pytest_collection_modifyitems(config, items):
    repo_root = Path(str(config.rootdir))
    for item in items:
        test_path = Path(str(item.fspath))
        try:
            rel_path = test_path.relative_to(repo_root).as_posix()
        except ValueError:
            continue

        test_type = TEST_TYPE_BY_FILE.get(rel_path)
        if test_type in TEST_TYPE_MARKERS:
            item.add_marker(getattr(pytest.mark, test_type))


DDL_CUSTOMER = """
DROP TABLE IF EXISTS shop_dm.ods_customer;
CREATE TABLE IF NOT EXISTS shop_dm.ods_customer (
    customer_id   BIGINT       NOT NULL COMMENT '客户ID',
    customer_name VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender        VARCHAR(4)   NULL COMMENT '性别',
    age           INT          NULL COMMENT '年龄',
    phone         VARCHAR(20)  NULL COMMENT '手机号',
    email         VARCHAR(128) NULL COMMENT '邮箱',
    address       VARCHAR(256) NULL COMMENT '地址',
    city          VARCHAR(64)  NULL COMMENT '城市',
    province      VARCHAR(64)  NULL COMMENT '省份',
    member_level  VARCHAR(16)  NULL COMMENT '会员等级',
    register_date DATE         NULL COMMENT '注册日期',
    create_time   DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_ORDER = """
DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id       BIGINT        NOT NULL COMMENT '订单ID',
    customer_id    BIGINT        NOT NULL COMMENT '客户ID',
    store_id       BIGINT        NOT NULL COMMENT '门店ID',
    order_date     DATE          NOT NULL COMMENT '订单日期',
    total_amount   DECIMAL(12,2) NOT NULL COMMENT '订单总额',
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    payment_amount DECIMAL(12,2) NOT NULL COMMENT '实付金额',
    payment_method VARCHAR(16)   NULL COMMENT '支付方式',
    order_status   VARCHAR(16)   NOT NULL DEFAULT '已完成' COMMENT '订单状态',
    promotion_id   BIGINT        NULL COMMENT '促销活动ID',
    create_time    DATETIME      NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_DWD_CUSTOMER = """
DROP TABLE IF EXISTS shop_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_customer (
    customer_id    BIGINT       NOT NULL COMMENT '客户ID',
    customer_name  VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender         VARCHAR(4)   NULL COMMENT '性别',
    age            INT          NULL COMMENT '年龄',
    age_group      VARCHAR(16)  NULL COMMENT '年龄段',
    phone          VARCHAR(20)  NULL COMMENT '手机号',
    email          VARCHAR(128) NULL COMMENT '邮箱',
    address        VARCHAR(256) NULL COMMENT '地址',
    city           VARCHAR(64)  NULL COMMENT '城市',
    province       VARCHAR(64)  NULL COMMENT '省份',
    member_level   VARCHAR(16)  NULL COMMENT '会员等级',
    register_date  DATE         NULL COMMENT '注册日期',
    etl_time       DATETIME     NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_PROJECTION = """
DROP TABLE IF EXISTS shop_dm.ads_sales_dashboard;
CREATE TABLE IF NOT EXISTS shop_dm.ads_sales_dashboard (
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    total_orders     BIGINT        NULL COMMENT '订单总数',
    avg_order_amount DECIMAL(10,2) NULL COMMENT '平均客单价',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
DUPLICATE KEY(stat_date)
DISTRIBUTED BY HASH(stat_date) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""


@pytest.fixture
def schema_ods_order():
    return {
        "shop_dm": {
            "ods_order": {
                "order_id": "BIGINT",
                "customer_id": "BIGINT",
                "store_id": "BIGINT",
                "order_date": "DATE",
                "total_amount": "DECIMAL(12,2)",
                "discount_amount": "DECIMAL(12,2)",
                "payment_amount": "DECIMAL(12,2)",
                "payment_method": "VARCHAR(16)",
                "order_status": "VARCHAR(16)",
                "promotion_id": "BIGINT",
                "create_time": "DATETIME",
            }
        }
    }


@pytest.fixture
def schema_ods_customer():
    return {
        "shop_dm": {
            "ods_customer": {
                "customer_id": "BIGINT",
                "customer_name": "VARCHAR(64)",
                "gender": "VARCHAR(4)",
                "age": "INT",
                "phone": "VARCHAR(20)",
                "email": "VARCHAR(128)",
                "address": "VARCHAR(256)",
                "city": "VARCHAR(64)",
                "province": "VARCHAR(64)",
                "member_level": "VARCHAR(16)",
                "register_date": "DATE",
                "create_time": "DATETIME",
            }
        }
    }


@pytest.fixture
def schema_dwd_customer():
    return {
        "shop_dm": {
            "dwd_customer": {
                "customer_id": "BIGINT",
                "customer_name": "VARCHAR(64)",
                "gender": "VARCHAR(4)",
                "age": "INT",
                "age_group": "VARCHAR(16)",
                "phone": "VARCHAR(20)",
                "email": "VARCHAR(128)",
                "address": "VARCHAR(256)",
                "city": "VARCHAR(64)",
                "province": "VARCHAR(64)",
                "member_level": "VARCHAR(16)",
                "register_date": "DATE",
                "etl_time": "DATETIME",
            }
        }
    }


@pytest.fixture
def schema_all(schema_ods_order, schema_ods_customer, schema_dwd_customer):
    schema = {}
    for s in [schema_ods_order, schema_ods_customer, schema_dwd_customer]:
        for db, tables in s.items():
            schema.setdefault(db, {}).update(tables)
    return schema


@pytest.fixture
def ddl_dir(tmp_path):
    d = tmp_path / "ddl"
    d.mkdir()
    (d / "ods_customer.sql").write_text(DDL_CUSTOMER)
    (d / "ods_order.sql").write_text(DDL_ORDER)
    (d / "dwd_customer.sql").write_text(DDL_DWD_CUSTOMER)
    (d / "ads_sales_dashboard.sql").write_text(DDL_PROJECTION)
    return d


@pytest.fixture
def ddl_texts():
    return [DDL_CUSTOMER, DDL_ORDER, DDL_DWD_CUSTOMER, DDL_PROJECTION]
