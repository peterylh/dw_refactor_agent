-- DWD 商品维度宽表
-- table_id: a7d83b46-0937-444c-81be-161a8996e580
DROP TABLE IF EXISTS shop_dm.dwd_product;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_product (
    product_id        BIGINT        NOT NULL COMMENT '商品ID',
    snapshot_date     DATE          NOT NULL COMMENT '快照日期',
    etl_time          DATETIME      NOT NULL COMMENT 'ETL处理时间',
    product_name      VARCHAR(128)  NOT NULL COMMENT '商品名称',
    category_id       BIGINT        NOT NULL COMMENT '品类ID',
    category_name     VARCHAR(64)   NULL COMMENT '品类名称',
    parent_category_id BIGINT       NULL COMMENT '上级品类ID',
    category_level    TINYINT       NULL COMMENT '品类层级',
    brand             VARCHAR(64)   NULL COMMENT '品牌',
    unit              VARCHAR(16)   NOT NULL COMMENT '单位',
    unit_price        DECIMAL(12,2) NOT NULL COMMENT '单价',
    cost_price        DECIMAL(12,2) NOT NULL COMMENT '成本价',
    gross_margin      DECIMAL(5,2)  NULL COMMENT '毛利率',
    spec              VARCHAR(64)   NULL COMMENT '规格',
    barcode           VARCHAR(32)   NULL COMMENT '条形码',
    status            TINYINT       NOT NULL DEFAULT 1 COMMENT '状态'
) ENGINE=OLAP
UNIQUE KEY(product_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
