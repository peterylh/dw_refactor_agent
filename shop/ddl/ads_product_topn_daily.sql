-- ADS 商品日销售排行TOP N表
-- table_id: 208649ff-2988-4a90-b1a6-1359c8334e18
DROP TABLE IF EXISTS shop_dm.ads_product_topn_daily;
CREATE TABLE IF NOT EXISTS shop_dm.ads_product_topn_daily (
    stat_date      DATE          NOT NULL COMMENT '统计日期',
    product_id     BIGINT        NOT NULL COMMENT '商品ID',
    product_name   VARCHAR(128)  NULL COMMENT '商品名称',
    category_name  VARCHAR(64)   NULL COMMENT '品类名称',
    sale_quantity  INT           NULL COMMENT '销售数量',
    sale_amount    DECIMAL(14,2) NULL COMMENT '销售金额',
    rank_num       INT           NULL COMMENT '排名',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date, product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
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
