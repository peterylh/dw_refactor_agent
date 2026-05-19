-- 表级血缘关系表
DROP TABLE IF EXISTS table_lineage;
CREATE TABLE IF NOT EXISTS table_lineage (
    id              BIGINT NOT NULL COMMENT '记录ID',
    source_table_id BIGINT NOT NULL COMMENT '上游来源表ID',
    target_table_id BIGINT NOT NULL COMMENT '下游目标表ID',
    job_id          BIGINT NULL COMMENT '加工作业ID'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO table_lineage VALUES
(1, 1, 2, 1);
