-- ADS Olist 商品销售排行表
-- table_id: 23db7c6f-c66c-4b23-9ed2-2f59add87663
DROP TABLE IF EXISTS olist_dm.ads_product_topn;
CREATE TABLE IF NOT EXISTS olist_dm.ads_product_topn (
    stat_date       DATE          NOT NULL COMMENT '统计日期',
    product_id      VARCHAR(64)   NOT NULL COMMENT '商品ID',
    product_category_name_english VARCHAR(64) NULL COMMENT '品类英语名称',
    item_count      INT           NULL COMMENT '销售件数',
    total_revenue   DECIMAL(14,2) NULL COMMENT '销售额',
    avg_price       DECIMAL(10,2) NULL COMMENT '平均售价',
    rank_num        INT           NULL COMMENT '排名',
    etl_time        DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(stat_date, product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
