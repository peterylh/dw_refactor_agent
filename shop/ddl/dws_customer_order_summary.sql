-- DWS 客户订单汇总表
DROP TABLE IF EXISTS shop_dm.dws_customer_order_summary;
CREATE TABLE IF NOT EXISTS shop_dm.dws_customer_order_summary (
    customer_id      BIGINT        NOT NULL COMMENT '客户ID',
    stat_date        DATE          NOT NULL COMMENT '统计日期',
    order_count      INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    total_amount     DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '订单总额',
    total_discount   DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '折扣总额',
    payment_amount   DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '实付总额',
    avg_order_amount DECIMAL(10,2) NULL COMMENT '平均客单价',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id, stat_date)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
