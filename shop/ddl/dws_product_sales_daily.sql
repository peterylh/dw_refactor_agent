-- DWS 商品日销售汇总表
DROP TABLE IF EXISTS shop_dm.dws_product_sales_daily;
CREATE TABLE IF NOT EXISTS shop_dm.dws_product_sales_daily (
    product_id      BIGINT        NOT NULL COMMENT '商品ID',
    stat_date       DATE          NOT NULL COMMENT '统计日期',
    order_count     INT           NOT NULL DEFAULT 0 COMMENT '订单笔数',
    sale_quantity   INT           NOT NULL DEFAULT 0 COMMENT '销售数量',
    sale_amount     DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '销售金额',
    discount_amount DECIMAL(14,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    etl_time        DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(product_id, stat_date)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
