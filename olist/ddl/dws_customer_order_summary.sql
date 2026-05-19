-- DWS Olist 客户订单汇总表
-- table_id: 79790dde-df2d-4550-a7c7-b9cbe70d9c59
DROP TABLE IF EXISTS olist_dm.dws_customer_order_summary;
CREATE TABLE IF NOT EXISTS olist_dm.dws_customer_order_summary (
    customer_id      VARCHAR(64)   NOT NULL COMMENT '客户ID',
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    order_count      INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    total_price      DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '商品总价',
    total_freight    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总运费',
    total_revenue    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总收入',
    avg_order_value  DECIMAL(10,2) NULL COMMENT '平均订单价值',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id, stat_date)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
