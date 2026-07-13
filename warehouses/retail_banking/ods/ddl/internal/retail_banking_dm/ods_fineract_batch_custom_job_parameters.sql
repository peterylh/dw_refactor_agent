-- ODS mirror of Apache Fineract batch_custom_job_parameters (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_batch_custom_job_parameters;
-- table_id: 2b7a27dd-a4f9-43fe-82e0-118ad6fdc200
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_batch_custom_job_parameters (
    -- column_id: 0f036817-8850-43f4-bafa-20ba5d605134
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1f16f360-ebce-4b44-b513-4c4e9e2fa4e7
    `parameter_json` STRING NOT NULL COMMENT 'Fineract source column parameter_json',
    -- column_id: 2d3dc009-8866-4799-9356-0da300ebd8a2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
