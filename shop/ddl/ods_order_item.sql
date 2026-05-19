-- ODS 订单明细表
-- table_id: 3ef976ba-17e4-49ca-83c1-85f1163e192f
DROP TABLE IF EXISTS shop_dm.ods_order_item;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order_item (
    order_item_id BIGINT        NOT NULL COMMENT '订单明细ID',
    order_id      BIGINT        NOT NULL COMMENT '订单ID',
    product_id    BIGINT        NOT NULL COMMENT '商品ID',
    quantity      INT           NOT NULL COMMENT '数量',
    unit_price    DECIMAL(12,2) NOT NULL COMMENT '单价',
    discount      DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    subtotal      DECIMAL(12,2) NOT NULL COMMENT '小计',
    create_time   DATETIME      NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(order_item_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(order_item_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
