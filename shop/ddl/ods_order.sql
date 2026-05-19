-- ODS 订单主表
-- table_id: a17bb555-fc22-4ef5-807d-497a9d950295
DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id       BIGINT        NOT NULL COMMENT '订单ID',
    customer_id    BIGINT        NOT NULL COMMENT '客户ID',
    store_id       BIGINT        NOT NULL COMMENT '门店ID',
    order_date     DATE          NOT NULL COMMENT '订单日期',
    total_amount   DECIMAL(12,2) NOT NULL COMMENT '订单总额',
    discount_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '折扣金额',
    payment_amount DECIMAL(12,2) NOT NULL COMMENT '实付金额',
    payment_method VARCHAR(16)   NULL COMMENT '支付方式:微信/支付宝/银行卡/现金',
    order_status   VARCHAR(16)   NOT NULL DEFAULT '已完成' COMMENT '订单状态:已完成/已取消/退货',
    promotion_id   BIGINT        NULL COMMENT '促销活动ID',
    create_time    DATETIME      NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
