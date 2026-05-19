-- DWS 品类月度销售汇总表
-- table_id: e424c979-4953-4c9a-b9d6-19ae25b4b180
DROP TABLE IF EXISTS shop_dm.dws_category_sales_monthly;
CREATE TABLE IF NOT EXISTS shop_dm.dws_category_sales_monthly (
    category_id    BIGINT        NOT NULL COMMENT '品类ID',
    stat_month     VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    stat_month_date DATE         NOT NULL COMMENT '统计月份(月初日期)',
    order_count    INT           NOT NULL DEFAULT 0 COMMENT '订单笔数',
    sale_quantity  INT           NOT NULL DEFAULT 0 COMMENT '销售数量',
    sale_amount    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '销售金额',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(category_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202501 VALUES LESS THAN ("2025-02-01"),
    PARTITION p202502 VALUES LESS THAN ("2025-03-01"),
    PARTITION p202503 VALUES LESS THAN ("2025-04-01"),
    PARTITION p202504 VALUES LESS THAN ("2025-05-01"),
    PARTITION p202505 VALUES LESS THAN ("2025-06-01"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(category_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
