-- DWS Olist 卖家月度销售汇总
DROP TABLE IF EXISTS olist_dm.dws_seller_monthly;
CREATE TABLE IF NOT EXISTS olist_dm.dws_seller_monthly (
    seller_id        VARCHAR(64)   NOT NULL COMMENT '卖家ID',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    order_count      INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    item_count       INT           NOT NULL DEFAULT 0 COMMENT '商品件数',
    total_revenue    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总收入(含运费)',
    total_price      DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '商品总价',
    total_freight    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总运费',
    avg_review_score DECIMAL(3,2)  NULL COMMENT '平均评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(seller_id, stat_month)
DISTRIBUTED BY HASH(seller_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
