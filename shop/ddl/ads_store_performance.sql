-- ADS 门店绩效评估表
-- table_id: b6e00810-e675-41a8-bc53-22b826fa1e23
DROP TABLE IF EXISTS shop_dm.ads_store_performance;
CREATE TABLE IF NOT EXISTS shop_dm.ads_store_performance (
    store_id         BIGINT        NOT NULL COMMENT '门店ID',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    stat_month_date  DATE          NOT NULL COMMENT '统计月份(月初日期)',
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
UNIQUE KEY(store_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
    PARTITION p202502 VALUES LESS THAN ("2025-03-01"),
    PARTITION p202503 VALUES LESS THAN ("2025-04-01"),
    PARTITION p202504 VALUES LESS THAN ("2025-05-01"),
    PARTITION p202505 VALUES LESS THAN ("2025-06-01"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
