-- ODS Olist 订单主表
-- table_id: d38b509b-4a34-44fb-ac6e-b5d7dff08eae
DROP TABLE IF EXISTS olist_dm.ods_order;
CREATE TABLE IF NOT EXISTS olist_dm.ods_order (
    order_id                   VARCHAR(64) NOT NULL COMMENT '订单ID',
    customer_id                VARCHAR(64) NOT NULL COMMENT '客户ID',
    order_status               VARCHAR(32) NOT NULL COMMENT '订单状态:delivered/shipped/canceled/unavailable/invoiced/processing/approved/created',
    order_purchase_timestamp   DATETIME    NULL COMMENT '下单时间',
    order_approved_at          DATETIME    NULL COMMENT '审核通过时间',
    order_delivered_carrier_date DATETIME  NULL COMMENT '承运商发货时间',
    order_delivered_customer_date DATETIME NULL COMMENT '客户签收时间',
    order_estimated_delivery_date DATETIME  NULL COMMENT '预计送达时间'
) ENGINE=OLAP
DUPLICATE KEY(order_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_order VALUES
('e481f51cbdc54678b7cc49136f2d6af7', '06b8999e2fba1a1fbc88172c00ba8bc7', 'delivered', '2017-10-02 10:56:33', '2017-10-02 11:07:15', '2017-10-04 19:55:00', '2017-10-10 21:25:13', '2017-10-18 00:00:00'),
('b81ef226eb4b103634d32c90c15332e2', '189c805f1c00fc9667f57f64529b9752', 'delivered', '2018-07-28 20:36:29', '2018-07-29 02:58:49', '2018-07-31 13:32:26', '2018-08-03 18:02:23', '2018-08-15 00:00:00'),
('283f5b7d0cb7315c7ce3a25f3d2c7cbb', '3442b82b0e1029e20214fadd84aa6ceb', 'delivered', '2018-07-08 20:08:51', '2018-07-08 21:38:39', '2018-07-11 15:33:27', '2018-07-18 16:33:29', '2018-07-25 00:00:00'),
('35525498cf846e15db751b6e1c09c995', 'b2b3c9e92c1ddbe35e9c00f81fad2a4c', 'delivered', '2017-07-10 10:18:01', '2017-07-10 10:29:35', '2017-07-13 11:49:31', '2017-07-18 15:06:18', '2017-07-27 00:00:00'),
('2a45c8b93b1d0e1c25f20a09bb6a9fbe', 'cec48eb9493bdedcce09e2dcc40f7bcf', 'delivered', '2018-06-09 17:24:56', '2018-06-09 18:29:26', '2018-06-11 13:18:19', '2018-06-13 16:25:24', '2018-06-29 00:00:00');
