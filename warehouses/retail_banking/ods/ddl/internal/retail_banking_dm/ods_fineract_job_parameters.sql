-- ODS mirror of Apache Fineract job_parameters (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_job_parameters;
-- table_id: 8eed5c35-0394-41e4-b61a-24fcc93f55c4
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_job_parameters (
    -- column_id: 904b2acf-475f-4fa6-93f2-0beb851fe12d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4b257575-69c5-4e0a-ac07-894f29777b68
    `job_id` BIGINT NOT NULL COMMENT 'Fineract source column job_id',
    -- column_id: f9b98cb2-4e6b-40fb-baa2-41d83c1c297a
    `parameter_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column parameter_name',
    -- column_id: 880dd21c-adbf-48e2-aa4f-5f5eda17db7b
    `parameter_value` STRING NOT NULL COMMENT 'Fineract source column parameter_value',
    -- column_id: 9ca52906-5464-430d-afdc-d20fcc9c2854
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
