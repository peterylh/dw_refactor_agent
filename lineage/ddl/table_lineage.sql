-- 表级血缘关系表
DROP TABLE IF EXISTS table_lineage;
CREATE TABLE IF NOT EXISTS table_lineage (
    snapshot_id     BIGINT      NOT NULL COMMENT '所属血缘快照ID',
    target_table_id BIGINT      NOT NULL COMMENT '下游目标表ID，快照内唯一',
    source_table_id BIGINT      NOT NULL COMMENT '上游来源表ID，快照内唯一',
    relation_type   VARCHAR(32) NOT NULL COMMENT '关系类型: direct/FILTER/GROUP_BY/JOIN_ON/HAVING',
    id              BIGINT      NOT NULL COMMENT '记录ID，快照内唯一',
    job_id          BIGINT      NULL COMMENT '加工作业ID，快照内唯一'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, target_table_id, source_table_id, relation_type, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
