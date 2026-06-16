-- 间接血缘表(WHERE/JOIN_ON/GROUP_BY/HAVING 条件依赖)
DROP TABLE IF EXISTS indirect_lineage;
CREATE TABLE IF NOT EXISTS indirect_lineage (
    snapshot_id          BIGINT      NOT NULL COMMENT '所属血缘快照ID',
    target_table_id      BIGINT      NOT NULL COMMENT '受影响的目标表ID，快照内唯一',
    source_table_id      BIGINT      NOT NULL COMMENT '来源表ID(被引用的字段所属表)，快照内唯一',
    source_column_id     BIGINT      NOT NULL COMMENT '来源字段ID，快照内唯一',
    condition_type       VARCHAR(32) NOT NULL COMMENT '条件类型: WHERE/JOIN_ON/GROUP_BY/HAVING/FILTER',
    id                   BIGINT      NOT NULL COMMENT '记录ID，快照内唯一',
    job_id               BIGINT      NOT NULL COMMENT '加工作业ID，快照内唯一',
    condition_expression TEXT        NULL COMMENT '原始条件片段'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, target_table_id, source_table_id, source_column_id, condition_type, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
