-- DWD Olist 客户明细维表(纯维度)
DROP TABLE IF EXISTS olist_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS olist_dm.dwd_customer (
    customer_id          VARCHAR(64) NOT NULL COMMENT '客户ID',
    customer_unique_id   VARCHAR(64) NOT NULL COMMENT '客户唯一标识',
    customer_city        VARCHAR(64) NULL COMMENT '城市',
    customer_state       VARCHAR(4)  NULL COMMENT '州缩写',
    customer_region      VARCHAR(32) NULL COMMENT '地理区域:Norte/Nordeste/Centro-Oeste/Sudeste/Sul',
    etl_time             DATETIME    NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
