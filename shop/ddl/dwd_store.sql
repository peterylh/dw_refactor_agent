-- DWD 门店维度宽表
DROP TABLE IF EXISTS shop_dm.dwd_store;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_store (
    store_id     BIGINT        NOT NULL COMMENT '门店ID',
    store_name   VARCHAR(128)  NOT NULL COMMENT '门店名称',
    store_type   VARCHAR(32)   NULL COMMENT '门店类型',
    store_level  VARCHAR(16)   NULL COMMENT '门店级别:A级/B级/C级',
    address      VARCHAR(256)  NULL COMMENT '地址',
    city         VARCHAR(64)   NULL COMMENT '城市',
    province     VARCHAR(64)   NULL COMMENT '省份',
    area_size    DECIMAL(8,2)  NULL COMMENT '面积(平方米)',
    open_date    DATE          NULL COMMENT '开业日期',
    open_years   DECIMAL(4,1)  NULL COMMENT '开业年限(年,含小数)',
    status       TINYINT       NOT NULL DEFAULT 1 COMMENT '状态',
    etl_time     DATETIME      NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(store_id)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
