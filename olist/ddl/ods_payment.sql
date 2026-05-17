-- ODS Olist 订单支付表
DROP TABLE IF EXISTS olist_dm.ods_payment;
CREATE TABLE IF NOT EXISTS olist_dm.ods_payment (
    order_id            VARCHAR(64)   NOT NULL COMMENT '订单ID',
    payment_sequential  INT           NOT NULL COMMENT '支付序号(分期时多行)',
    payment_type        VARCHAR(32)   NOT NULL COMMENT '支付方式:credit_card/boleto/voucher/debit_card/not_defined',
    payment_installments INT          NOT NULL COMMENT '分期期数',
    payment_value       DECIMAL(12,2) NOT NULL COMMENT '支付金额'
) ENGINE=OLAP
DUPLICATE KEY(order_id, payment_sequential)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_payment VALUES
('e481f51cbdc54678b7cc49136f2d6af7', 1, 'credit_card', 1, 72.19),
('b81ef226eb4b103634d32c90c15332e2', 1, 'boleto', 1, 28.36),
('283f5b7d0cb7315c7ce3a25f3d2c7cbb', 1, 'credit_card', 6, 81.44);
