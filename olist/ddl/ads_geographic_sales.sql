-- ADS Olist 地理销售分析表
-- table_id: 883314ce-ea9f-477c-b94d-d7fc14dda961
DROP TABLE IF EXISTS olist_dm.ads_geographic_sales;
CREATE TABLE IF NOT EXISTS olist_dm.ads_geographic_sales (
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    customer_state   VARCHAR(4)    NOT NULL COMMENT '客户州缩写',
    customer_region  VARCHAR(32)   NULL COMMENT '地理区域',
    order_count      INT           NULL COMMENT '订单数',
    customer_count   INT           NULL COMMENT '客户数(去重)',
    total_revenue    DECIMAL(14,2) NULL COMMENT '总收入',
    avg_freight      DECIMAL(10,2) NULL COMMENT '平均运费',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_month, customer_state)
DISTRIBUTED BY HASH(customer_state) BUCKETS 10
PROPERTIES ("replication_num" = "1");
