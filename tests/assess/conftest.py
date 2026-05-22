"""共享 fixture: DDL/ETL 样本、mock API 响应"""

import pytest
from dataclasses import dataclass


# ============================================================
# 样本 DDL — 维度表
# ============================================================

DDL_DWD_CUSTOMER = """\
-- DWD 客户明细宽表
DROP TABLE IF EXISTS shop_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_customer (
    customer_id    BIGINT       NOT NULL COMMENT '客户ID',
    snapshot_date  DATE         NOT NULL COMMENT '快照日期',
    etl_time       DATETIME     NOT NULL COMMENT 'ETL处理时间',
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
    register_date  DATE         NULL COMMENT '注册日期'
) ENGINE=OLAP
UNIQUE KEY(customer_id, snapshot_date)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

ETL_DWD_CUSTOMER = """\
SET @etl_date = COALESCE(@etl_date, CURDATE());
INSERT INTO shop_dm.dwd_customer
SELECT
    customer_id,
    CAST(@etl_date AS DATE) AS snapshot_date,
    NOW() AS etl_time,
    customer_name, gender, age,
    CASE WHEN age < 30 THEN '青年' WHEN age < 45 THEN '中年'
         WHEN age < 60 THEN '中老年' ELSE '老年' END AS age_group,
    phone, email, address, city, province, member_level, register_date
FROM shop_dm.ods_customer;
"""

# ============================================================
# 样本 DDL — 事实表
# ============================================================

DDL_DWD_ORDER_DETAIL = """\
-- DWD 订单明细事实表
DROP TABLE IF EXISTS shop_dm.dwd_order_detail;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_order_detail (
    order_item_id  BIGINT        NOT NULL COMMENT '订单明细ID',
    order_id       BIGINT        NOT NULL COMMENT '订单ID',
    customer_id    BIGINT        NOT NULL COMMENT '客户ID',
    store_id       BIGINT        NOT NULL COMMENT '门店ID',
    product_id     BIGINT        NOT NULL COMMENT '商品ID',
    category_id    INT           NOT NULL COMMENT '类目ID',
    promotion_id   BIGINT        NULL COMMENT '促销活动ID',
    order_date     DATE          NOT NULL COMMENT '订单日期',
    order_month    VARCHAR(7)    NULL COMMENT '订单月份',
    quantity       INT           NOT NULL COMMENT '数量',
    unit_price     DECIMAL(10,2) NOT NULL COMMENT '单价',
    discount       DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    subtotal       DECIMAL(12,2) NOT NULL COMMENT '小计金额',
    cost_price     DECIMAL(10,2) NULL COMMENT '成本价',
    gross_profit   DECIMAL(12,2) NULL COMMENT '毛利',
    payment_method VARCHAR(16)   NULL COMMENT '支付方式',
    order_status   VARCHAR(16)   NOT NULL COMMENT '订单状态',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(order_item_id)
DISTRIBUTED BY HASH(order_item_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

ETL_DWD_ORDER_DETAIL = """\
TRUNCATE TABLE shop_dm.dwd_order_detail;
INSERT INTO shop_dm.dwd_order_detail
SELECT
    oi.order_item_id, o.order_id, o.customer_id, o.store_id,
    oi.product_id, p.category_id, o.promotion_id,
    o.order_date,
    DATE_FORMAT(o.order_date, '%Y-%m') AS order_month,
    oi.quantity, oi.unit_price, oi.discount, oi.subtotal,
    p.cost_price,
    oi.subtotal - oi.quantity * p.cost_price AS gross_profit,
    o.payment_method, o.order_status,
    NOW() AS etl_time
FROM shop_dm.ods_order_item oi
INNER JOIN shop_dm.ods_order o ON oi.order_id = o.order_id
LEFT JOIN shop_dm.ods_product p ON oi.product_id = p.product_id;
"""

# ============================================================
# 样本 DDL — DWS 汇总表 (事实)
# ============================================================

DDL_DWS_STORE_SALES = """\
-- DWS 门店销售日汇总
DROP TABLE IF EXISTS shop_dm.dws_store_sales_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_store_sales_daily (
    store_id       BIGINT        NOT NULL COMMENT '门店ID',
    stat_date      DATE          NOT NULL COMMENT '统计日期',
    order_count    INT           NULL COMMENT '订单数',
    total_amount   DECIMAL(12,2) NULL COMMENT '销售总额',
    customer_count INT           NULL COMMENT '客户数',
    payment_amount DECIMAL(12,2) NULL COMMENT '实付金额',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_date)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

ETL_DWS_STORE_SALES = """\
TRUNCATE TABLE shop_dm.dws_store_sales_daily;
INSERT INTO shop_dm.dws_store_sales_daily
SELECT
    store_id, order_date AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    SUM(subtotal) AS total_amount,
    COUNT(DISTINCT customer_id) AS customer_count,
    SUM(subtotal - discount) AS payment_amount,
    NOW() AS etl_time
FROM shop_dm.dwd_order_detail
GROUP BY store_id, order_date;
"""

# ============================================================
# 样本血缘数据
# ============================================================


@pytest.fixture
def sample_lineage_data():
    """模拟 lineage_data.json 的最小结构"""
    return {
        "tables": [
            {
                "name": "dwd_customer",
                "full_name": "shop_dm.dwd_customer",
                "layer": "DWD",
                "columns": [
                    {"name": "customer_id", "type": "BIGINT"},
                    {"name": "customer_name", "type": "VARCHAR(64)"},
                    {"name": "gender", "type": "VARCHAR(4)"},
                    {"name": "age", "type": "INT"},
                    {"name": "city", "type": "VARCHAR(64)"},
                ],
            },
            {
                "name": "dwd_order_detail",
                "full_name": "shop_dm.dwd_order_detail",
                "layer": "DWD",
                "columns": [
                    {"name": "order_item_id", "type": "BIGINT"},
                    {"name": "order_id", "type": "BIGINT"},
                    {"name": "customer_id", "type": "BIGINT"},
                    {"name": "subtotal", "type": "DECIMAL(12,2)"},
                    {"name": "quantity", "type": "INT"},
                ],
            },
            {
                "name": "dws_store_sales_daily",
                "full_name": "shop_dm.dws_store_sales_daily",
                "layer": "DWS",
                "columns": [
                    {"name": "store_id", "type": "BIGINT"},
                    {"name": "stat_date", "type": "DATE"},
                    {"name": "order_count", "type": "INT"},
                    {"name": "total_amount", "type": "DECIMAL(12,2)"},
                ],
            },
            {
                "name": "ads_sales_dashboard",
                "full_name": "shop_dm.ads_sales_dashboard",
                "layer": "ADS",
                "columns": [
                    {"name": "stat_date", "type": "DATE"},
                    {"name": "total_orders", "type": "BIGINT"},
                ],
            },
        ],
        "edges": [
            {"source": "ods_customer.customer_id", "target": "dwd_customer.customer_id",
             "expression": "customer_id", "source_file": "dwd_customer.sql"},
            {"source": "dwd_order_detail.order_id", "target": "dws_store_sales_daily.order_count",
             "expression": "COUNT(DISTINCT order_id)", "source_file": "dws_store_sales_daily.sql"},
            {"source": "dwd_customer.customer_id", "target": "ads_sales_dashboard.total_orders",
             "expression": "customer_id", "source_file": "ads_sales_dashboard.sql"},
        ],
        "indirect_edges": [],
    }


# ============================================================
# Mock API 响应
# ============================================================

MOCK_DIMENSION_RESPONSE = {
    "choices": [{
        "message": {
            "content": '{"table_type": "dimension", "confidence": 0.95, "reason": "描述客户实体属性,无可聚合度量字段"}'
        }
    }]
}

MOCK_FACT_RESPONSE = {
    "choices": [{
        "message": {
            "content": '{"table_type": "fact", "confidence": 0.92, "reason": "包含订单交易明细,有subtotal/quantity等可聚合度量"}'
        }
    }]
}

MOCK_OTHER_RESPONSE = {
    "choices": [{
        "message": {
            "content": '{"table_type": "other", "confidence": 0.6, "reason": "桥接表,处理多对多关系"}'
        }
    }]
}

MOCK_MARKDOWN_WRAPPED_RESPONSE = {
    "choices": [{
        "message": {
            "content": '```json\n{"table_type": "dimension", "confidence": 0.9, "reason": "维度表"}\n```'
        }
    }]
}

MOCK_MALFORMED_RESPONSE = {
    "choices": [{
        "message": {
            "content": "这是一个维度表，因为它描述了客户属性"
        }
    }]
}
