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
PARTITION BY RANGE(stat_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(store_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
