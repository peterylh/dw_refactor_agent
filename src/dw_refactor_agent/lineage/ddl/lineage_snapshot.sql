-- 血缘快照表：记录每次导入批次，并标记当前 active 快照
DROP TABLE IF EXISTS lineage_snapshot;
CREATE TABLE IF NOT EXISTS lineage_snapshot (
    project                VARCHAR(64)  NOT NULL COMMENT '项目名称: shop/finance_analytics',
    id                     BIGINT       NOT NULL COMMENT '快照ID，默认由导入脚本按当前时间毫秒生成',
    source_path            VARCHAR(512) NULL COMMENT '导入来源 lineage_data JSON 路径',
    imported_at            DATETIME     NOT NULL COMMENT '导入时间',
    status                 VARCHAR(16)  NOT NULL COMMENT '状态: IMPORTED/ACTIVE/FAILED',
    is_active              TINYINT      NOT NULL DEFAULT 0 COMMENT '是否为当前对外查询快照',
    table_count            BIGINT       NOT NULL DEFAULT 0 COMMENT '表数量',
    column_count           BIGINT       NOT NULL DEFAULT 0 COMMENT '字段数量',
    job_count              BIGINT       NOT NULL DEFAULT 0 COMMENT '作业数量',
    job_dataset_count      BIGINT       NOT NULL DEFAULT 0 COMMENT '作业输入输出关系数量',
    column_lineage_count   BIGINT       NOT NULL DEFAULT 0 COMMENT '直接字段血缘数量',
    non_column_direct_lineage_count BIGINT NOT NULL DEFAULT 0 COMMENT '非字段来源直接血缘数量',
    indirect_lineage_count BIGINT       NOT NULL DEFAULT 0 COMMENT '间接血缘数量',
    table_lineage_count    BIGINT       NOT NULL DEFAULT 0 COMMENT '表级血缘数量'
) ENGINE=OLAP
UNIQUE KEY(project, id)
DISTRIBUTED BY HASH(project) BUCKETS 10
PROPERTIES ("replication_num" = "1");
