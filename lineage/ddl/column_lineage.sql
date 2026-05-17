-- 字段级直接血缘表
DROP TABLE IF EXISTS column_lineage;
CREATE TABLE IF NOT EXISTS column_lineage (
    id                BIGINT       NOT NULL COMMENT '记录ID',
    source_table_id   BIGINT       NOT NULL COMMENT '来源表ID',
    source_column_id  BIGINT       NOT NULL COMMENT '来源字段ID',
    target_table_id   BIGINT       NOT NULL COMMENT '目标表ID',
    target_column_id  BIGINT       NOT NULL COMMENT '目标字段ID',
    job_id            BIGINT       NULL COMMENT '加工作业ID',
    expression        TEXT         NULL COMMENT '转换表达式'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO column_lineage VALUES
(1, 1, 1, 2, 1, 1, 'o.id');
