-- 表元数据表
DROP TABLE IF EXISTS lineage.table_info;
CREATE TABLE IF NOT EXISTS lineage.table_info (
    id            BIGINT      NOT NULL COMMENT '表ID',
    datasource_id BIGINT      NOT NULL COMMENT '所属数据源ID',
    table_name    VARCHAR(64) NOT NULL COMMENT '表名(不含库名)',
    full_name     VARCHAR(128) NOT NULL COMMENT '全限定名: shop_dm.ods_order',
    layer         VARCHAR(16) NULL COMMENT '分层: ODS/DWD/DWS/ADS/DIM/OTHER'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO lineage.table_info VALUES
(1, 1, 'ods_order', 'shop_dm.ods_order', 'ODS'),
(2, 1, 'dwd_order_detail', 'shop_dm.dwd_order_detail', 'DWD'),
(3, 1, 'dws_store_sales_daily', 'shop_dm.dws_store_sales_daily', 'DWS'),
(4, 1, 'ads_sales_dashboard', 'shop_dm.ads_sales_dashboard', 'ADS');
