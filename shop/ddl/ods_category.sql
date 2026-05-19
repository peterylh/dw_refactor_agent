-- ODS 商品品类表
-- table_id: bf1e1a62-7080-419d-bcba-448c95b0f068
DROP TABLE IF EXISTS shop_dm.ods_category;
CREATE TABLE IF NOT EXISTS shop_dm.ods_category (
    category_id        BIGINT      NOT NULL COMMENT '品类ID',
    category_name      VARCHAR(64) NOT NULL COMMENT '品类名称',
    parent_category_id BIGINT      NULL COMMENT '上级品类ID',
    category_level     TINYINT     NOT NULL COMMENT '品类层级:1/2/3',
    sort_order         INT         NULL COMMENT '排序',
    create_time        DATETIME    NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(category_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(category_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);
