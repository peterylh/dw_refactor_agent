-- ODS mirror of Apache Fineract c_external_service_properties (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_c_external_service_properties;
-- table_id: 2b5fa734-1f77-4492-be11-be8d05b527e5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_c_external_service_properties (
    -- column_id: 30f97e07-b8f7-4310-9e7e-c70e03f2c735
    `name` VARCHAR(150) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 6c7b879f-9f2f-4948-840f-ba9d8267a301
    `value` VARCHAR(250) NULL COMMENT 'Fineract source column value',
    -- column_id: 16a18fc6-c66c-491e-8df0-274875ec2e88
    `external_service_id` BIGINT NOT NULL COMMENT 'Fineract source column external_service_id',
    -- column_id: c9213735-e73b-4564-8d81-a7c06ddeaf0b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`name`)
DISTRIBUTED BY HASH(`name`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
