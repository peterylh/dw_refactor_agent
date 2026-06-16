-- ETL 加工作业表
DROP TABLE IF EXISTS job;
CREATE TABLE IF NOT EXISTS job (
    snapshot_id BIGINT       NOT NULL COMMENT '所属血缘快照ID',
    source_file VARCHAR(256) NOT NULL COMMENT '任务 SQL 相对路径',
    id          BIGINT       NOT NULL COMMENT '作业ID，快照内唯一',
    job_name    VARCHAR(128) NOT NULL COMMENT '作业名称: dwd_order_detail',
    job_type    VARCHAR(16)  NULL COMMENT '作业类型: SQL/SHELL/SPARK',
    raw_sql     TEXT         NULL COMMENT '原始SQL文本'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, source_file, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
