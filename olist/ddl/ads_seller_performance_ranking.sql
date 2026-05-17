-- ADS Olist 卖家绩效排名表
DROP TABLE IF EXISTS olist_dm.ads_seller_performance_ranking;
CREATE TABLE IF NOT EXISTS olist_dm.ads_seller_performance_ranking (
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    seller_id        VARCHAR(64)   NOT NULL COMMENT '卖家ID',
    seller_city      VARCHAR(64)   NULL COMMENT '城市',
    seller_state     VARCHAR(4)    NULL COMMENT '州缩写',
    order_count      INT           NULL COMMENT '订单数',
    total_revenue    DECIMAL(14,2) NULL COMMENT '总收入',
    avg_review_score DECIMAL(3,2)  NULL COMMENT '平均评分',
    revenue_rank     INT           NULL COMMENT '收入排名',
    score_rank       INT           NULL COMMENT '评分排名',
    performance_score DECIMAL(5,2) NULL COMMENT '综合绩效评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_month, seller_id)
DISTRIBUTED BY HASH(seller_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
