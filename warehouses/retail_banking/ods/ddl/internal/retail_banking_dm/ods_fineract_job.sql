-- ODS mirror of Apache Fineract job (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_job;
-- table_id: 55d91968-3ed6-4ff2-adf8-2f4a0a5b65ba
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_job (
    -- column_id: c0b997b1-19d6-46e8-9139-36d8f1d27478
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c90dd425-9ea4-4cc0-851a-646344b53ba2
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 733907b7-3b18-4ddb-ab51-e1eff14b79f7
    `display_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: c07a856c-51b8-46ea-89fd-6080c3500287
    `cron_expression` VARCHAR(20) NOT NULL COMMENT 'Fineract source column cron_expression',
    -- column_id: 18fcde3d-33e9-40db-8a20-8ea7931300da
    `create_time` DATETIME NOT NULL COMMENT 'Fineract source column create_time',
    -- column_id: 19803999-6d66-4f21-aee0-7796b9c6943e
    `task_priority` SMALLINT NOT NULL COMMENT 'Fineract source column task_priority',
    -- column_id: 27b7369e-9439-4792-97da-9eb857ba1cdb
    `group_name` VARCHAR(50) NULL COMMENT 'Fineract source column group_name',
    -- column_id: e1264f13-a8dc-4b51-9995-ce435da40cd1
    `previous_run_start_time` DATETIME NULL COMMENT 'Fineract source column previous_run_start_time',
    -- column_id: da458b8c-6755-4f12-99d4-bd3f28a48172
    `next_run_time` DATETIME NULL COMMENT 'Fineract source column next_run_time',
    -- column_id: 7d4b6ef4-a29a-454e-b556-4495ed0393c1
    `job_key` VARCHAR(500) NULL COMMENT 'Fineract source column job_key',
    -- column_id: 74353409-d7ee-4eef-856b-83e306e0b36c
    `initializing_errorlog` STRING NULL COMMENT 'Fineract source column initializing_errorlog',
    -- column_id: a61af23f-cc62-4267-9a1c-afa265f9b08e
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: c0b88482-3fc7-4660-b527-b38a758aad90
    `currently_running` BOOLEAN NOT NULL COMMENT 'Fineract source column currently_running',
    -- column_id: 1e4b6600-7eed-4f32-a33a-935c60589d00
    `updates_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column updates_allowed',
    -- column_id: e93ae03e-9523-424e-91ac-071d45dd4779
    `scheduler_group` SMALLINT NOT NULL COMMENT 'Fineract source column scheduler_group',
    -- column_id: 9e77da88-35a8-4142-90ef-12c3b9c48194
    `is_misfired` BOOLEAN NOT NULL COMMENT 'Fineract source column is_misfired',
    -- column_id: 24e81d4f-c055-46b5-843d-756f7f7a49c1
    `node_id` INT NULL COMMENT 'Fineract source column node_id',
    -- column_id: 678457a1-5e7c-420b-b405-5f05a67f03a0
    `is_mismatched_job` BOOLEAN NULL COMMENT 'Fineract source column is_mismatched_job',
    -- column_id: 571619ea-659f-4f54-bb37-bed169a4a242
    `short_name` VARCHAR(8) NOT NULL COMMENT 'Fineract source column short_name',
    -- column_id: 465f3b4e-cb15-41da-86f9-a16e15c77d5f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
