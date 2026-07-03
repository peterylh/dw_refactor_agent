-- 数据源配置表
DROP TABLE IF EXISTS datasource;
CREATE TABLE IF NOT EXISTS datasource (
    snapshot_id BIGINT       NOT NULL COMMENT '所属血缘快照ID',
    project     VARCHAR(64)  NOT NULL COMMENT '项目名称',
    id          BIGINT       NOT NULL COMMENT '数据源ID，快照内唯一',
    name        VARCHAR(128) NOT NULL COMMENT '业务库名: shop_dm',
    db_type     VARCHAR(32)  NOT NULL COMMENT '数据库类型: doris/mysql/starrocks',
    host        VARCHAR(128) NULL COMMENT '连接地址: IP:Port'
) ENGINE=OLAP
DUPLICATE KEY(snapshot_id, project, id)
DISTRIBUTED BY HASH(snapshot_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
