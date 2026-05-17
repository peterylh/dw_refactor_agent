-- DWD Olist 订单明细事实表
DROP TABLE IF EXISTS olist_dm.dwd_order_detail;
CREATE TABLE IF NOT EXISTS olist_dm.dwd_order_detail (
    order_id                VARCHAR(64)   NOT NULL COMMENT '订单ID',
    order_item_id           INT           NOT NULL COMMENT '订单内商品序号',
    customer_id             VARCHAR(64)   NOT NULL COMMENT '客户ID',
    seller_id               VARCHAR(64)   NOT NULL COMMENT '卖家ID',
    product_id              VARCHAR(64)   NOT NULL COMMENT '商品ID',
    product_category_name   VARCHAR(64)   NULL COMMENT '商品品类(葡萄牙语)',
    product_category_name_english VARCHAR(64) NULL COMMENT '商品品类(英语)',
    order_status            VARCHAR(32)   NOT NULL COMMENT '订单状态',
    order_purchase_timestamp DATETIME     NULL COMMENT '下单时间',
    order_delivered_customer_date DATETIME NULL COMMENT '客户签收时间',
    order_estimated_delivery_date DATETIME NULL COMMENT '预计送达时间',
    order_month             VARCHAR(7)    NULL COMMENT '订单月份:YYYY-MM',
    price                   DECIMAL(12,2) NOT NULL COMMENT '商品单价',
    freight_value           DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '运费',
    payment_type            VARCHAR(32)   NULL COMMENT '支付方式',
    payment_installments    INT           NULL COMMENT '分期期数',
    review_score            INT           NULL COMMENT '评价评分:1-5',
    delivery_days           INT           NULL COMMENT '实际配送天数',
    estimated_delivery_days INT           NULL COMMENT '预计配送天数',
    delivery_delay_days     INT           NULL COMMENT '配送延迟天数(正数=延迟)',
    etl_time                DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(order_id, order_item_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
