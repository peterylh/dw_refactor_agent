-- 非字段来源（字面量/表达式）的字段级直接血缘表
DROP TABLE IF EXISTS non_column_direct_lineage;
CREATE TABLE IF NOT EXISTS non_column_direct_lineage (
    snapshot_id         BIGINT      NOT NULL COMMENT '所属血缘快照ID',
    target_table_id     BIGINT      NOT NULL COMMENT '目标表ID，快照内唯一',
    target_column_id    BIGINT      NOT NULL COMMENT '目标字段ID，快照内唯一',
    source_type         VARCHAR(32) NOT NULL COMMENT '来源类型: literal/expression',
    id                  BIGINT      NOT NULL COMMENT '记录ID，快照内唯一',
    job_id              BIGINT      NOT NULL COMMENT '加工作业ID，快照内唯一',
    relation_type       VARCHAR(32) NOT NULL COMMENT '关系类型: direct',
    transformation_type VARCHAR(32) NULL COMMENT '转换类型: constant/calculation',
    expression          TEXT        NULL COMMENT '转换表达式',
    source_payload      TEXT        NOT NULL COMMENT '完整来源引用 JSON，保留标量类型'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, target_table_id, target_column_id, source_type, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
