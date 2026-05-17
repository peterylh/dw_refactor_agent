-- ODS Olist 订单明细表
DROP TABLE IF EXISTS olist_dm.ods_order_item;
CREATE TABLE IF NOT EXISTS olist_dm.ods_order_item (
    order_id          VARCHAR(64)   NOT NULL COMMENT '订单ID',
    order_item_id     INT           NOT NULL COMMENT '订单内商品序号',
    product_id        VARCHAR(64)   NOT NULL COMMENT '商品ID',
    seller_id         VARCHAR(64)   NOT NULL COMMENT '卖家ID',
    shipping_limit_date DATETIME    NULL COMMENT '承运商发货截止时间',
    price             DECIMAL(12,2) NOT NULL COMMENT '商品单价',
    freight_value     DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '运费'
) ENGINE=OLAP
DUPLICATE KEY(order_id, order_item_id)
DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_order_item VALUES
('e481f51cbdc54678b7cc49136f2d6af7', 1, '99a4788cb24856965c36a24e339b6058', 'a2f422f53b83c5a2b261b63a1fa6b76f', '2017-10-06 00:00:00', 58.90, 13.29),
('b81ef226eb4b103634d32c90c15332e2', 1, 'e5a5a36a10b770a434cdabdffe57c3b2', '27c110563e7c8c9758c4fe651340eae3', '2018-08-01 00:00:00', 19.90, 8.46),
('283f5b7d0cb7315c7ce3a25f3d2c7cbb', 1, '785546fb8ab0a484607add1ba1be23f7', '1025f0e2d44d7041d6cf58b6550e0bfa', '2018-07-11 00:00:00', 69.90, 11.54);
