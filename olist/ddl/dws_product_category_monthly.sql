-- DWS Olist 品类月度销售汇总
-- table_id: 74294541-b7fe-4468-ba35-dbfdf4c5482a
DROP TABLE IF EXISTS olist_dm.dws_product_category_monthly;
CREATE TABLE IF NOT EXISTS olist_dm.dws_product_category_monthly (
    product_category_name_english VARCHAR(64) NOT NULL COMMENT '品类英语名称',
    stat_month       VARCHAR(7)    NOT NULL COMMENT '统计月份:YYYY-MM',
    order_count      INT           NOT NULL DEFAULT 0 COMMENT '订单数',
    item_count       INT           NOT NULL DEFAULT 0 COMMENT '商品件数',
    total_revenue    DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '总收入',
    avg_price        DECIMAL(10,2) NULL COMMENT '平均单价',
    avg_freight      DECIMAL(10,2) NULL COMMENT '平均运费',
    avg_review_score DECIMAL(3,2)  NULL COMMENT '平均评分',
    etl_time         DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(product_category_name_english, stat_month)
DISTRIBUTED BY HASH(product_category_name_english) BUCKETS 10
PROPERTIES ("replication_num" = "1");
