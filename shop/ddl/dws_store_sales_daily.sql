-- DWS 门店日销售汇总表
-- table_id: c888836b-b989-4845-998f-882c362cca3f
DROP TABLE IF EXISTS shop_dm.dws_store_sales_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_store_sales_daily (
    store_id        BIGINT        NOT NULL COMMENT '门店ID',
    stat_date       DATE          NOT NULL COMMENT '统计日期',
    order_count     INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    customer_count  INT           NOT NULL DEFAULT 0 COMMENT '客户数(去重)',
    total_amount    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '订单总额',
    discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    payment_amount  DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '实付金额',
    etl_time        DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_date)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PARTITION BY RANGE(stat_date) (
    PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
    PARTITION p202502 VALUES LESS THAN ("2025-03-01"),
    PARTITION p202503 VALUES LESS THAN ("2025-04-01"),
    PARTITION p202504 VALUES LESS THAN ("2025-05-01"),
    PARTITION p202505 VALUES LESS THAN ("2025-06-01"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
PROPERTIES (
    "replication_num" = "1"
);
