-- 表元数据表
DROP TABLE IF EXISTS table_info;
CREATE TABLE IF NOT EXISTS table_info (
    snapshot_id       BIGINT       NOT NULL COMMENT '所属血缘快照ID',
    table_name        VARCHAR(128) NOT NULL COMMENT '表名(不含库名)',
    id                BIGINT       NOT NULL COMMENT '表ID，快照内唯一',
    datasource_id     BIGINT       NOT NULL COMMENT '所属数据源ID，快照内唯一',
    full_name         VARCHAR(256) NOT NULL COMMENT '全限定名: shop_dm.ods_order',
    dataset_type      VARCHAR(16)  NOT NULL DEFAULT 'managed' COMMENT '数据集类型: managed/process/temporary/external',
    is_transient      TINYINT      NOT NULL DEFAULT 0 COMMENT '是否为解析过程中的临时表/CTE',
    transient_sources TEXT         NULL COMMENT '临时表来源，JSON 数组'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, table_name, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
