-- DWD 门店维度宽表
-- table_id: 93c07cba-3c14-4486-9a5d-ddee38caaf4c
DROP TABLE IF EXISTS shop_dm.dwd_store;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_store (
    store_id     BIGINT        NOT NULL COMMENT '门店ID',
    snapshot_date DATE         NOT NULL COMMENT '快照日期',
    etl_time     DATETIME      NOT NULL COMMENT 'ETL处理时间',
    store_name   VARCHAR(128)  NOT NULL COMMENT '门店名称',
    store_type   VARCHAR(32)   NULL COMMENT '门店类型',
    store_level  VARCHAR(16)   NULL COMMENT '门店级别:A级/B级/C级',
    address      VARCHAR(256)  NULL COMMENT '地址',
    city         VARCHAR(64)   NULL COMMENT '城市',
    province     VARCHAR(64)   NULL COMMENT '省份',
    area_size    DECIMAL(8,2)  NULL COMMENT '面积(平方米)',
    open_date    DATE          NULL COMMENT '开业日期',
    open_years   DECIMAL(4,1)  NULL COMMENT '开业年限(年,含小数)',
    status       TINYINT       NOT NULL DEFAULT 1 COMMENT '状态'
) ENGINE=OLAP
UNIQUE KEY(store_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(store_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
