-- 列元数据表
DROP TABLE IF EXISTS lineage.column_info;
CREATE TABLE IF NOT EXISTS lineage.column_info (
    id          BIGINT       NOT NULL COMMENT '列ID',
    table_id    BIGINT       NOT NULL COMMENT '所属表ID',
    column_name VARCHAR(64)  NOT NULL COMMENT '列名',
    data_type   VARCHAR(32)  NULL COMMENT '数据类型: BIGINT/DECIMAL(12,2)/VARCHAR(64)',
    comment     VARCHAR(256) NULL COMMENT '字段说明',
    ordinal     INT          NULL COMMENT '字段排序序号'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO lineage.column_info VALUES
(1, 1, 'id', 'BIGINT', '订单ID', 0),
(2, 1, 'customer_id', 'BIGINT', '客户ID', 1),
(3, 1, 'order_date', 'DATE', '订单日期', 2);
