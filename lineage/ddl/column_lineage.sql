-- 字段级直接血缘表
DROP TABLE IF EXISTS column_lineage;
CREATE TABLE IF NOT EXISTS column_lineage (
    snapshot_id         BIGINT      NOT NULL COMMENT '所属血缘快照ID',
    target_table_id     BIGINT      NOT NULL COMMENT '目标表ID，快照内唯一',
    target_column_id    BIGINT      NOT NULL COMMENT '目标字段ID，快照内唯一',
    source_table_id     BIGINT      NOT NULL COMMENT '来源表ID，快照内唯一',
    source_column_id    BIGINT      NOT NULL COMMENT '来源字段ID，快照内唯一',
    id                  BIGINT      NOT NULL COMMENT '记录ID，快照内唯一',
    job_id              BIGINT      NULL COMMENT '加工作业ID，快照内唯一',
    relation_type       VARCHAR(32) NOT NULL COMMENT '关系类型: direct',
    transformation_type VARCHAR(32) NULL COMMENT '转换类型: passthrough/aggregation/constant',
    expression          TEXT        NULL COMMENT '转换表达式'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, target_table_id, target_column_id, source_table_id, source_column_id, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
