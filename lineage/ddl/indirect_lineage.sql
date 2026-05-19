-- 间接血缘表(WHERE/JOIN_ON/GROUP_BY/HAVING 条件依赖)
DROP TABLE IF EXISTS indirect_lineage;
CREATE TABLE IF NOT EXISTS indirect_lineage (
    id                   BIGINT       NOT NULL COMMENT '记录ID',
    source_table_id      BIGINT       NOT NULL COMMENT '来源表ID(被引用的字段所属表)',
    source_column_id     BIGINT       NOT NULL COMMENT '来源字段ID',
    target_table_id      BIGINT       NOT NULL COMMENT '受影响的目标表ID',
    job_id               BIGINT       NOT NULL COMMENT '加工作业ID',
    condition_type       VARCHAR(20)  NOT NULL COMMENT '条件类型: WHERE/JOIN_ON/GROUP_BY/HAVING',
    condition_expression TEXT         NULL COMMENT '原始条件片段'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO indirect_lineage VALUES
(1, 1, 2, 2, 1, 'WHERE', 'o.order_status = ''已完成''');
