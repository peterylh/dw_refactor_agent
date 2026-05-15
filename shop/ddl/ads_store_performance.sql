-- ADS 门店绩效评估表
DROP TABLE IF EXISTS shop_dm.ads_store_performance;
CREATE TABLE IF NOT EXISTS shop_dm.ads_store_performance (
    store_id         BIGINT        NOT NULL COMMENT '门店ID',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    store_name       VARCHAR(128)  NULL COMMENT '门店名称',
    city             VARCHAR(64)   NULL COMMENT '城市',
    store_type       VARCHAR(32)   NULL COMMENT '门店类型',
    total_orders     INT           NULL COMMENT '总订单数',
    total_amount     DECIMAL(14,2) NULL COMMENT '总销售额',
    customer_count   INT           NULL COMMENT '客户数',
    avg_order_amount DECIMAL(10,2) NULL COMMENT '客单价',
    performance_score DECIMAL(5,2) NULL COMMENT '绩效评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id, stat_month)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
