-- 数据源配置表
DROP TABLE IF EXISTS datasource;
CREATE TABLE IF NOT EXISTS datasource (
    id      BIGINT      NOT NULL COMMENT '数据源ID',
    name    VARCHAR(64) NOT NULL COMMENT '数据源名称: shop_dm',
    db_type VARCHAR(32) NOT NULL COMMENT '数据库类型: starrocks/mysql',
    host    VARCHAR(128) NULL COMMENT '连接地址: IP:Port'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO datasource VALUES
(1, 'shop_dm',  'starrocks', '172.16.0.90:9030'),
(2, 'olist_dm', 'starrocks', '172.16.0.90:9030');
