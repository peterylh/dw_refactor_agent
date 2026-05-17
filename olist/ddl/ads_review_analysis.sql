-- ADS Olist 评价分析表
DROP TABLE IF EXISTS olist_dm.ads_review_analysis;
CREATE TABLE IF NOT EXISTS olist_dm.ads_review_analysis (
    stat_month        VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    review_score      INT           NOT NULL COMMENT '评分:1-5',
    review_count      INT           NULL COMMENT '评价数',
    score_pct         DECIMAL(5,2)  NULL COMMENT '占比(%)',
    avg_delivery_days DECIMAL(6,2)  NULL COMMENT '该评分下平均配送天数',
    etl_time          DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_month, review_score)
DISTRIBUTED BY HASH(review_score) BUCKETS 10
PROPERTIES ("replication_num" = "1");
