-- ODS Olist 地理位置表
-- table_id: e8bfee9d-6c64-4af4-a41d-2c1b7743828e
DROP TABLE IF EXISTS olist_dm.ods_geolocation;
CREATE TABLE IF NOT EXISTS olist_dm.ods_geolocation (
    geolocation_zip_code_prefix VARCHAR(8)    NOT NULL COMMENT '邮编前缀',
    geolocation_lat            DECIMAL(10,7) NULL COMMENT '纬度',
    geolocation_lng            DECIMAL(10,7) NULL COMMENT '经度',
    geolocation_city           VARCHAR(64)   NULL COMMENT '城市',
    geolocation_state          VARCHAR(4)    NULL COMMENT '州缩写'
) ENGINE=OLAP
DUPLICATE KEY(geolocation_zip_code_prefix)
DISTRIBUTED BY HASH(geolocation_zip_code_prefix) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_geolocation VALUES
('01001', -23.5453000, -46.6428000, 'sao paulo', 'SP'),
('01002', -23.5478000, -46.6395000, 'sao paulo', 'SP'),
('01003', -23.5467000, -46.6366000, 'sao paulo', 'SP'),
('01004', -23.5482000, -46.6339000, 'sao paulo', 'SP'),
('01005', -23.5491000, -46.6308000, 'sao paulo', 'SP');
