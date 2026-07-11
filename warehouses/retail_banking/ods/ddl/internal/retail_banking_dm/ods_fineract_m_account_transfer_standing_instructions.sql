-- ODS mirror of Apache Fineract m_account_transfer_standing_instructions (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions;
-- table_id: 334e5de8-e48f-43ff-8880-6cfc2443cb45
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions (
    -- column_id: f6c427b8-9c7a-41fa-8cef-7c807cfe190f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cc6e0f0d-acfa-4943-9063-f24e06d51b60
    `name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 45622167-2f0e-4f32-8951-f22d1aa8fd8f
    `account_transfer_details_id` BIGINT NOT NULL COMMENT 'Fineract source column account_transfer_details_id',
    -- column_id: 2a50456d-0df6-4acc-a9ba-ce215a11238f
    `priority` TINYINT NOT NULL COMMENT 'Fineract source column priority',
    -- column_id: b952de67-f1a8-4add-b045-acc7f3292a84
    `status` TINYINT NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 44fccf48-6e7a-4e0b-a411-e83389cdcdf5
    `instruction_type` TINYINT NOT NULL COMMENT 'Fineract source column instruction_type',
    -- column_id: 3cc1e6e0-2197-401d-a756-9aa8f79920d3
    `amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount',
    -- column_id: c0ad7ffb-c2ac-4f96-9b97-f4191e17da57
    `valid_from` DATE NOT NULL COMMENT 'Fineract source column valid_from',
    -- column_id: 178559c8-84c4-4573-bb81-448fd24fb2f3
    `valid_till` DATE NULL COMMENT 'Fineract source column valid_till',
    -- column_id: 757db3de-bfb1-4148-b9e7-cfe44ca0ad82
    `recurrence_type` TINYINT NOT NULL COMMENT 'Fineract source column recurrence_type',
    -- column_id: a07d9020-fe6c-4eee-8a19-f48cdbf2a3e6
    `recurrence_frequency` SMALLINT NULL COMMENT 'Fineract source column recurrence_frequency',
    -- column_id: f1b36070-f7ca-4c7b-ae30-c26c2cb1bd9e
    `recurrence_interval` SMALLINT NULL COMMENT 'Fineract source column recurrence_interval',
    -- column_id: ca704691-3d5b-46b9-8338-c0ae6bba3207
    `recurrence_on_day` SMALLINT NULL COMMENT 'Fineract source column recurrence_on_day',
    -- column_id: 18747506-7db7-457f-84c3-49522a9b35bd
    `recurrence_on_month` SMALLINT NULL COMMENT 'Fineract source column recurrence_on_month',
    -- column_id: b1611012-73fe-4f02-a17e-4085b2b622d2
    `last_run_date` DATE NULL COMMENT 'Fineract source column last_run_date',
    -- column_id: 99ec3efe-f9a1-495b-bb54-d933df218913
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
