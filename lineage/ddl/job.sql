-- ETL 加工作业表
DROP TABLE IF EXISTS lineage.job;
CREATE TABLE IF NOT EXISTS lineage.job (
    id       BIGINT       NOT NULL COMMENT '作业ID',
    job_name VARCHAR(128) NOT NULL COMMENT '作业名称: dwd_order_detail',
    job_type VARCHAR(16)  NULL COMMENT '作业类型: SQL/SHELL/SPARK',
    raw_sql  TEXT         NULL COMMENT '原始SQL文本'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO lineage.job VALUES
(1, 'dwd_order_detail', 'SQL', 'INSERT INTO shop_dm.dwd_order_detail SELECT ...');
