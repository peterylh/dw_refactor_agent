-- ODS 门店信息表
-- table_id: 9b80e880-ad2c-444d-92c5-c01b8130a0a1
DROP TABLE IF EXISTS shop_dm.ods_store;
CREATE TABLE IF NOT EXISTS shop_dm.ods_store (
    store_id    BIGINT       NOT NULL COMMENT '门店ID',
    store_name  VARCHAR(128) NOT NULL COMMENT '门店名称',
    store_type  VARCHAR(32)  NULL COMMENT '门店类型:旗舰店/标准店/社区店',
    address     VARCHAR(256) NULL COMMENT '地址',
    city        VARCHAR(64)  NULL COMMENT '城市',
    province    VARCHAR(64)  NULL COMMENT '省份',
    area_size   DECIMAL(8,2) NULL COMMENT '面积(平方米)',
    open_date   DATE         NULL COMMENT '开业日期',
    status      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态:1营业/0歇业',
    create_time DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(store_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(store_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
