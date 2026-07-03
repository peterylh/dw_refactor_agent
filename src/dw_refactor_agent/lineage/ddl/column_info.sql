-- 列元数据表
DROP TABLE IF EXISTS column_info;
CREATE TABLE IF NOT EXISTS column_info (
    snapshot_id BIGINT       NOT NULL COMMENT '所属血缘快照ID',
    table_id    BIGINT       NOT NULL COMMENT '所属表ID，快照内唯一',
    column_name VARCHAR(128) NOT NULL COMMENT '列名',
    id          BIGINT       NOT NULL COMMENT '列ID，快照内唯一',
    data_type   VARCHAR(128) NULL COMMENT '数据类型: BIGINT/DECIMAL(12,2)/VARCHAR(64)',
    comment     VARCHAR(512) NULL COMMENT '字段说明',
    ordinal     INT          NULL COMMENT '字段排序序号'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, table_id, column_name, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
