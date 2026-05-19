-- ODS 库存记录表
-- table_id: 6930c57e-9d4f-43ed-b276-a160e4031d6c
DROP TABLE IF EXISTS shop_dm.ods_inventory;
CREATE TABLE IF NOT EXISTS shop_dm.ods_inventory (
    inventory_id    BIGINT   NOT NULL COMMENT '库存记录ID',
    product_id      BIGINT   NOT NULL COMMENT '商品ID',
    store_id        BIGINT   NOT NULL COMMENT '门店ID',
    quantity        INT      NOT NULL COMMENT '库存数量',
    safety_stock    INT      NOT NULL DEFAULT 10 COMMENT '安全库存',
    last_restock_date DATE   NULL COMMENT '最近补货日期',
    update_time     DATETIME NOT NULL COMMENT '更新时间',
    create_time     DATETIME NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(inventory_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(inventory_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
