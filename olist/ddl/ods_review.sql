-- ODS Olist 订单评价表
-- table_id: fb989fdd-8e28-460c-bc1a-4ee1e7e72fc0
DROP TABLE IF EXISTS olist_dm.ods_review;
CREATE TABLE IF NOT EXISTS olist_dm.ods_review (
    review_id               VARCHAR(64) NOT NULL COMMENT '评价ID',
    order_id                VARCHAR(64) NOT NULL COMMENT '订单ID',
    review_score            INT         NOT NULL COMMENT '评分:1-5',
    review_comment_title    VARCHAR(128) NULL COMMENT '评价标题',
    review_comment_message  STRING      NULL COMMENT '评价内容',
    review_creation_date    DATETIME    NULL COMMENT '评价创建时间',
    review_answer_timestamp DATETIME    NULL COMMENT '评价回复时间'
) ENGINE=OLAP
DUPLICATE KEY(review_id)
DISTRIBUTED BY HASH(review_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_review VALUES
('7b06c1e3f7e0ee9f7f79ec39e5fb099d', 'e481f51cbdc54678b7cc49136f2d6af7', 5, NULL, 'Produto muito bom.', '2017-10-13 18:39:17', '2017-10-13 18:39:17'),
('dd7503df5cb1afafb2a2c1e60c11fb97', 'b81ef226eb4b103634d32c90c15332e2', 5, NULL, 'Gostei muito, entrega rápida!', '2018-08-06 13:33:29', '2018-08-06 13:33:29'),
('890c3b2dd3de02ca6b5c18d6b0056ff4', '283f5b7d0cb7315c7ce3a25f3d2c7cbb', 1, NULL, 'Não gostei do produto.', '2018-07-23 17:36:11', '2018-07-23 17:36:11');
