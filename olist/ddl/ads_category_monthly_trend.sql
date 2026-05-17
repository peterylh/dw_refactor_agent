-- ADS Olist 品类月度趋势分析表
DROP TABLE IF EXISTS olist_dm.ads_category_monthly_trend;
CREATE TABLE IF NOT EXISTS olist_dm.ads_category_monthly_trend (
    product_category_name_english VARCHAR(64) NOT NULL COMMENT '品类英语名称',
    stat_month     VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    order_count    INT           NULL COMMENT '订单数',
    item_count     INT           NULL COMMENT '商品件数',
    total_revenue  DECIMAL(14,2) NULL COMMENT '总收入',
    avg_price      DECIMAL(10,2) NULL COMMENT '平均单价',
    avg_review_score DECIMAL(3,2) NULL COMMENT '平均评分',
    revenue_growth_rate DECIMAL(5,2) NULL COMMENT '收入环比增长率(%)',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(product_category_name_english, stat_month)
DISTRIBUTED BY HASH(product_category_name_english) BUCKETS 10
PROPERTIES ("replication_num" = "1");
