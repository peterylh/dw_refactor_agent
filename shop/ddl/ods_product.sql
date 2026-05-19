-- ODS 商品信息表
-- table_id: 1207263c-6522-4830-a666-14a1b616cf20
DROP TABLE IF EXISTS shop_dm.ods_product;
CREATE TABLE IF NOT EXISTS shop_dm.ods_product (
    product_id   BIGINT       NOT NULL COMMENT '商品ID',
    product_name VARCHAR(128) NOT NULL COMMENT '商品名称',
    category_id  BIGINT       NOT NULL COMMENT '品类ID',
    brand        VARCHAR(64)  NULL COMMENT '品牌',
    unit         VARCHAR(16)  NOT NULL COMMENT '单位:瓶/袋/盒/箱/个',
    unit_price   DECIMAL(12,2) NOT NULL COMMENT '单价(元)',
    cost_price   DECIMAL(12,2) NOT NULL COMMENT '成本价(元)',
    spec         VARCHAR(64)  NULL COMMENT '规格',
    barcode      VARCHAR(32)  NULL COMMENT '条形码',
    status       TINYINT      NOT NULL DEFAULT 1 COMMENT '状态:1上架/0下架',
    create_time  DATETIME     NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(product_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
