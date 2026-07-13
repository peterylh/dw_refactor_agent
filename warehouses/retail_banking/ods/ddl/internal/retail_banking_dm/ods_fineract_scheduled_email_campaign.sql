-- ODS mirror of Apache Fineract scheduled_email_campaign (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_scheduled_email_campaign;
-- table_id: 36fb9855-04a1-43bf-92c3-be618bcb1062
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_scheduled_email_campaign (
    -- column_id: 309eb3d9-c26c-4320-ab13-52a91b49e937
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c1ab5bd2-b232-4415-833f-68bfe963b4e1
    `campaign_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column campaign_name',
    -- column_id: 79bf2422-e57a-4d21-9dfb-ce93ce84073a
    `campaign_type` INT NOT NULL COMMENT 'Fineract source column campaign_type',
    -- column_id: 94ee2ac9-cc18-4965-946a-f288854af792
    `business_rule_id` INT NOT NULL COMMENT 'Fineract source column business_rule_id',
    -- column_id: 1688e660-af91-488f-880a-fe03207a53c8
    `param_value` STRING NULL COMMENT 'Fineract source column param_value',
    -- column_id: f9b9df2f-7cec-428f-94bf-63003005a778
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 7263b835-90be-4432-b4c3-65fda107990b
    `email_subject` VARCHAR(100) NOT NULL COMMENT 'Fineract source column email_subject',
    -- column_id: 3c3c6ad4-28d9-477a-9adf-16f7c18958ba
    `email_message` STRING NOT NULL COMMENT 'Fineract source column email_message',
    -- column_id: 35c42e6b-a3b4-4fcb-8527-2dcae38be0ed
    `email_attachment_file_format` VARCHAR(10) NULL COMMENT 'Fineract source column email_attachment_file_format',
    -- column_id: 1f4a4338-0388-4c2a-8143-abbac79eaf7c
    `stretchy_report_id` INT NULL COMMENT 'Fineract source column stretchy_report_id',
    -- column_id: 9f0ec2cb-72e4-4ea1-bf09-3949c53ca18f
    `stretchy_report_param_map` STRING NULL COMMENT 'Fineract source column stretchy_report_param_map',
    -- column_id: 60dbb89d-bb72-4541-a4c3-8386f6240375
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 4c00206a-1538-4b2a-b8b6-2c3dffb07a01
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 509433bf-6998-47b9-90d5-4266ee2d981d
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 6a837da2-935e-4185-8d59-44463bc772a2
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: 52f5776a-dd59-48e1-8fe1-8706db2061bd
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: f6fd7fe1-a4a0-4e50-990a-d63146abdcff
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: 58c5fb5c-0326-4be9-b004-aa3d08f7aae1
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: 56c1279d-ca5e-4af7-8697-39b533c3b876
    `next_trigger_date` DATETIME NULL COMMENT 'Fineract source column next_trigger_date',
    -- column_id: 9a69bf46-c5bc-4d11-8336-91727b372a11
    `last_trigger_date` DATETIME NULL COMMENT 'Fineract source column last_trigger_date',
    -- column_id: 9f6cf37b-65cc-407d-b4d7-9c7e25c2b886
    `recurrence_start_date` DATETIME NULL COMMENT 'Fineract source column recurrence_start_date',
    -- column_id: a1868efd-bdfa-4edf-b3b4-74a5d12e432a
    `is_visible` BOOLEAN NULL COMMENT 'Fineract source column is_visible',
    -- column_id: 93f4af38-40e3-45d0-a001-4c0aa726c139
    `previous_run_error_log` STRING NULL COMMENT 'Fineract source column previous_run_error_log',
    -- column_id: df09cb30-6f1e-448a-b6d2-45fecaf00f07
    `previous_run_error_message` STRING NULL COMMENT 'Fineract source column previous_run_error_message',
    -- column_id: 03b9fd0f-e17b-4153-a404-f8c4f57ca50a
    `previous_run_status` VARCHAR(10) NULL COMMENT 'Fineract source column previous_run_status',
    -- column_id: c4dde2a4-3926-47a6-bf34-edb0052c31ec
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
