-- ODS mirror of Apache Fineract job_run_history (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_job_run_history;
-- table_id: 875adb98-2f86-43b1-a3b6-dd55995be6fb
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_job_run_history (
    -- column_id: cbf8b779-e28c-4bc5-a0b9-ca08927e168d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7dd8fa76-37e6-4ee1-9788-5cbb439d8675
    `job_id` BIGINT NOT NULL COMMENT 'Fineract source column job_id',
    -- column_id: 2dbe0201-63cc-4172-a64d-ca0f71f9d09e
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 4f7307ed-a342-4abf-8621-48d4c2e11968
    `start_time` DATETIME NOT NULL COMMENT 'Fineract source column start_time',
    -- column_id: 9bdaaedd-9b04-405b-845a-3a2cd573af8c
    `end_time` DATETIME NOT NULL COMMENT 'Fineract source column end_time',
    -- column_id: 923759a3-1e2c-47ff-a46a-fc0ebd2418ae
    `status` VARCHAR(10) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: bc7aec32-f056-4941-ab10-80105d1c9a9a
    `error_message` STRING NULL COMMENT 'Fineract source column error_message',
    -- column_id: b78510f7-1997-46e7-83d5-c8f0272d1a19
    `trigger_type` VARCHAR(25) NOT NULL COMMENT 'Fineract source column trigger_type',
    -- column_id: 7df5a1e4-94aa-4bfb-b3af-c2da6d0155ac
    `error_log` STRING NULL COMMENT 'Fineract source column error_log',
    -- column_id: 88e3890b-c36b-4d1f-8e8a-dd7648ae45c1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
