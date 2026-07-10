-- DWS 品类月度销售汇总表
-- table_id: e424c979-4953-4c9a-b9d6-19ae25b4b180
DROP TABLE IF EXISTS shop_dm.dws_category_sales_monthly;
CREATE TABLE IF NOT EXISTS shop_dm.dws_category_sales_monthly (
    -- column_id: 98506d48-f151-4bf2-b2d8-a2963b5c3988
    category_id    BIGINT        NOT NULL COMMENT '品类ID',
    -- column_id: 47c1313a-3328-4005-840a-702729588d9a
    stat_month     VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    -- column_id: fc29c039-855f-40fa-ac02-cb84a1b26807
    stat_month_date DATE         NOT NULL COMMENT '统计月份(月初日期)',
    -- column_id: c2ccd301-6a40-45aa-9928-cc803337d375
    order_count    INT           NOT NULL DEFAULT 0 COMMENT '订单笔数',
    -- column_id: 51ed8fc8-e358-4305-b0ec-bf6bb3d95835
    sale_quantity  INT           NOT NULL DEFAULT 0 COMMENT '销售数量',
    -- column_id: e7457afa-cd13-4cc9-9701-d27503a29b72
    sale_amount    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '销售金额',
    -- column_id: 01af0829-54ac-4ca5-8c0b-42d6f584469a
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(category_id, stat_month, stat_month_date)
PARTITION BY RANGE(stat_month_date) (
    PARTITION p202406 VALUES LESS THAN ("2024-07-01"),
    PARTITION p202407 VALUES LESS THAN ("2024-08-01"),
    PARTITION p202408 VALUES LESS THAN ("2024-09-01"),
    PARTITION p202409 VALUES LESS THAN ("2024-10-01"),
    PARTITION p202410 VALUES LESS THAN ("2024-11-01"),
    PARTITION p202411 VALUES LESS THAN ("2024-12-01"),
    PARTITION p202412 VALUES LESS THAN ("2025-01-01"),
    PARTITION p202501 VALUES LESS THAN ("2025-02-01")
)
DISTRIBUTED BY HASH(category_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
