-- ODS mirror of Apache Fineract twofactor_configuration (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_twofactor_configuration;
-- table_id: 5cc8ea54-8ccc-451a-a1e1-840fc35f3e24
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_twofactor_configuration (
    -- column_id: cdf349ff-101a-4f36-9938-bcb6aa5fe3a4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ee0dddc3-c5e1-44be-9476-9c1fb64e6047
    `name` VARCHAR(40) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: d11c5000-ac8c-46e0-a208-11753bde64ac
    `value` VARCHAR(1024) NULL COMMENT 'Fineract source column value',
    -- column_id: 305ed66f-4b30-4121-8011-66d4009a5edc
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
