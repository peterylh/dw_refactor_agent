-- ODS Olist 客户信息表
DROP TABLE IF EXISTS olist_dm.ods_customer;
CREATE TABLE IF NOT EXISTS olist_dm.ods_customer (
    customer_id          VARCHAR(64)  NOT NULL COMMENT '客户ID',
    customer_unique_id   VARCHAR(64)  NOT NULL COMMENT '客户唯一标识',
    customer_zip_code_prefix VARCHAR(8)  NULL COMMENT '邮编前缀',
    customer_city        VARCHAR(64)  NULL COMMENT '城市',
    customer_state       VARCHAR(4)   NULL COMMENT '州缩写:SP/RJ/MG等'
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_customer VALUES
('06b8999e2fba1a1fbc88172c00ba8bc7', '861c471a50b7446e39b3717c272019c1', '14409', 'franca', 'SP'),
('189c805f1c00fc9667f57f64529b9752', '8d36e97b1231e9b0fc082a9a5b3f1e68', '09781', 'sao paulo', 'SP'),
('3442b82b0e1029e20214fadd84aa6ceb', '5373fc19b87e2edf99944be86943fc14', '11560', 'sao paulo', 'SP'),
('b2b3c9e92c1ddbe35e9c00f81fad2a4c', '5b086ad5f2a07a1af763e67cd3f2db59', '08474', 'sao paulo', 'SP'),
('cec48eb9493bdedcce09e2dcc40f7bcf', '3c085a1163bb9803f0f13b4655cd2baf', '13056', 'campinas', 'SP');
