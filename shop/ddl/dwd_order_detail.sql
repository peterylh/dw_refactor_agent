-- DWD 订单明细事实表
-- table_id: dd97001f-7b9a-412f-bdde-4f5a5ec0b76f
DROP TABLE IF EXISTS shop_dm.dwd_order_detail;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_order_detail (
    order_id        BIGINT        NOT NULL COMMENT '订单ID',
    order_item_id   BIGINT        NOT NULL COMMENT '订单明细ID',
    order_date      DATE          NOT NULL COMMENT '订单日期',
    customer_id     BIGINT        NOT NULL COMMENT '客户ID',
    store_id        BIGINT        NOT NULL COMMENT '门店ID',
    product_id      BIGINT        NOT NULL COMMENT '商品ID',
    category_id     BIGINT        NULL COMMENT '品类ID',
    promotion_id    BIGINT        NULL COMMENT '促销活动ID',
    order_month     VARCHAR(7)    NULL COMMENT '订单月份:YYYY-MM',
    quantity        INT           NOT NULL COMMENT '数量',
    unit_price      DECIMAL(12,2) NOT NULL COMMENT '单价',
    discount        DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    subtotal        DECIMAL(12,2) NOT NULL COMMENT '小计',
    cost_price      DECIMAL(12,2) NULL COMMENT '成本价',
    gross_profit    DECIMAL(12,2) NULL COMMENT '毛利',
    payment_method  VARCHAR(16)   NULL COMMENT '支付方式',
    order_status    VARCHAR(16)   NOT NULL DEFAULT '已完成' COMMENT '订单状态',
    etl_time        DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(order_id, order_item_id, order_date)
PARTITION BY RANGE(order_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(order_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
