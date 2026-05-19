-- DWS Olist 日订单汇总表
-- table_id: ac7874db-b66b-4ca9-a38d-34353b6e49b2
DROP TABLE IF EXISTS olist_dm.dws_daily_orders;
CREATE TABLE IF NOT EXISTS olist_dm.dws_daily_orders (
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    order_count      INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    customer_count   INT           NOT NULL DEFAULT 0 COMMENT '客户数(去重)',
    item_count       INT           NOT NULL DEFAULT 0 COMMENT '商品件数',
    total_revenue    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总收入',
    total_freight    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总运费',
    avg_order_value  DECIMAL(10,2) NULL COMMENT '平均订单价值',
    late_delivery_count INT       NOT NULL DEFAULT 0 COMMENT '延迟配送订单数',
    on_time_count    INT           NOT NULL DEFAULT 0 COMMENT '准时送达订单数',
    avg_delivery_days DECIMAL(6,2) NULL COMMENT '平均配送天数',
    avg_delay_days   DECIMAL(6,2)  NULL COMMENT '平均延迟天数(仅延迟订单)',
    max_delay_days   INT           NULL COMMENT '最大延迟天数',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date)
DISTRIBUTED BY HASH(stat_date) BUCKETS 10
PROPERTIES ("replication_num" = "1");
