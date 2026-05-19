-- DWD Olist 卖家明细维表(纯维度)
-- table_id: cf76c5af-3d52-47a9-a3ea-05ac4e43fbaf
DROP TABLE IF EXISTS olist_dm.dwd_seller;
CREATE TABLE IF NOT EXISTS olist_dm.dwd_seller (
    seller_id               VARCHAR(64) NOT NULL COMMENT '卖家ID',
    seller_city             VARCHAR(64) NULL COMMENT '城市',
    seller_state            VARCHAR(4)  NULL COMMENT '州缩写',
    seller_region           VARCHAR(32) NULL COMMENT '地理区域:Norte/Nordeste/Centro-Oeste/Sudeste/Sul',
    seller_zip_code_prefix  VARCHAR(8)  NULL COMMENT '邮编前缀',
    etl_time                DATETIME    NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(seller_id)
DISTRIBUTED BY HASH(seller_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
