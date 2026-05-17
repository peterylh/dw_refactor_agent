-- ODS Olist 卖家信息表
DROP TABLE IF EXISTS olist_dm.ods_seller;
CREATE TABLE IF NOT EXISTS olist_dm.ods_seller (
    seller_id               VARCHAR(64) NOT NULL COMMENT '卖家ID',
    seller_zip_code_prefix  VARCHAR(8)  NULL COMMENT '邮编前缀',
    seller_city             VARCHAR(64) NULL COMMENT '城市',
    seller_state            VARCHAR(4)  NULL COMMENT '州缩写'
) ENGINE=OLAP
DUPLICATE KEY(seller_id)
DISTRIBUTED BY HASH(seller_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_seller VALUES
('a2f422f53b83c5a2b261b63a1fa6b76f', '13053', 'campinas', 'SP'),
('27c110563e7c8c9758c4fe651340eae3', '05309', 'sao paulo', 'SP'),
('1025f0e2d44d7041d6cf58b6550e0bfa', '13041', 'campinas', 'SP');
