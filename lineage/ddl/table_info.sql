-- 表元数据表
DROP TABLE IF EXISTS table_info;
CREATE TABLE IF NOT EXISTS table_info (
    id            BIGINT      NOT NULL COMMENT '表ID',
    datasource_id BIGINT      NOT NULL COMMENT '所属数据源ID',
    table_name    VARCHAR(64) NOT NULL COMMENT '表名(不含库名)',
    full_name     VARCHAR(128) NOT NULL COMMENT '全限定名: shop_dm.ods_order',
    layer         VARCHAR(16) NULL COMMENT '分层: ODS/DWD/DWS/ADS/DIM/OTHER'
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO table_info VALUES
-- shop 项目
(1,    1, 'ods_order',          'shop_dm.ods_order',           'ODS'),
(2,    1, 'dwd_order_detail',   'shop_dm.dwd_order_detail',    'DWD'),
(3,    1, 'dws_store_sales_daily', 'shop_dm.dws_store_sales_daily', 'DWS'),
(4,    1, 'ads_sales_dashboard','shop_dm.ads_sales_dashboard', 'ADS'),
-- olist 项目 (offset 10000)
(10001, 2, 'ods_order',         'olist_dm.ods_order',          'ODS'),
(10002, 2, 'dwd_order_detail',  'olist_dm.dwd_order_detail',   'DWD'),
(10003, 2, 'dws_daily_orders',  'olist_dm.dws_daily_orders',   'DWS'),
(10004, 2, 'ads_customer_rfm',  'olist_dm.ads_customer_rfm',   'ADS');
