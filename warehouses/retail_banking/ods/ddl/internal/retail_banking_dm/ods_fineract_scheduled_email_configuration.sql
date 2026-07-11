-- ODS mirror of Apache Fineract scheduled_email_configuration (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_scheduled_email_configuration;
-- table_id: e8b0ed83-7532-4b3e-9f9f-fc97a6181056
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_scheduled_email_configuration (
    -- column_id: 03e2b52d-e6ff-46bf-ae76-a29e9832471a
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e4ad4c39-fbc8-4223-8ad3-2c7cc8edffc8
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 0e17b40c-fbfb-4589-a24c-70a59cb8f7b1
    `value` VARCHAR(200) NULL COMMENT 'Fineract source column value',
    -- column_id: 11307520-63d2-420c-9db9-ca41155385a2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
