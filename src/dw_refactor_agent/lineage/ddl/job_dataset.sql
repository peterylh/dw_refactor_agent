-- ETL 作业与输入输出数据集关系表
DROP TABLE IF EXISTS job_dataset;
CREATE TABLE IF NOT EXISTS job_dataset (
    snapshot_id BIGINT      NOT NULL COMMENT '所属血缘快照ID',
    job_id      BIGINT      NOT NULL COMMENT '作业ID，快照内唯一',
    table_id    BIGINT      NOT NULL COMMENT '数据集表ID，快照内唯一',
    io_type     VARCHAR(16) NOT NULL COMMENT '数据集角色: INPUT/OUTPUT'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, job_id, table_id, io_type)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
