-- ODS mirror of Apache Fineract sms_campaign (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_sms_campaign;
-- table_id: beeefc4b-3281-403c-bee6-efb35d174c57
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_sms_campaign (
    -- column_id: d3678a8c-0a35-4431-b817-0e5bceab3692
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2aabd950-de05-4fb9-b086-04d3d454503c
    `campaign_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column campaign_name',
    -- column_id: 86cf5729-b367-4f54-bf3f-d4ee692774d5
    `campaign_type` INT NOT NULL COMMENT 'Fineract source column campaign_type',
    -- column_id: e4a1ffd7-9893-4a9f-b255-b0760802f70d
    `campaign_trigger_type` INT NOT NULL COMMENT 'Fineract source column campaign_trigger_type',
    -- column_id: 7a4450da-3425-4ab9-b6bf-44b60a66338e
    `report_id` INT NOT NULL COMMENT 'Fineract source column report_id',
    -- column_id: 09a8f3f5-c1a5-4d09-925f-d8cba8185f16
    `provider_id` BIGINT NULL COMMENT 'Fineract source column provider_id',
    -- column_id: bdf428bf-90b2-4f0b-80d3-ff35a3c66543
    `param_value` STRING NULL COMMENT 'Fineract source column param_value',
    -- column_id: 4b506abd-24c5-45e1-a091-8ac19c6d808e
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 23eebed4-2bb2-41ce-9e14-87765ff997b2
    `message` STRING NOT NULL COMMENT 'Fineract source column message',
    -- column_id: 30b03570-e846-420d-b070-6d494bdc985f
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: f4152031-a6fa-4629-889c-3c4d05a4409b
    `submittedon_userid` BIGINT NULL COMMENT 'Fineract source column submittedon_userid',
    -- column_id: ca22e324-9d94-42b3-b2a5-883bdac00feb
    `approvedon_date` DATE NULL COMMENT 'Fineract source column approvedon_date',
    -- column_id: 1c2248e2-aae7-4516-9ee5-246b4089d16b
    `approvedon_userid` BIGINT NULL COMMENT 'Fineract source column approvedon_userid',
    -- column_id: e38f1e82-e72e-40d5-a74d-1ff8dc8dc121
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: 22b1a6ba-879d-4c30-bfdf-9047bf5d1c5c
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 6e411c2e-e79e-4fdf-8750-aa3a64f5d69e
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: 726ee8d1-fee9-4f30-b11f-047327922b7e
    `next_trigger_date` DATETIME NULL COMMENT 'Fineract source column next_trigger_date',
    -- column_id: 523336d2-2557-4078-92ee-d5ebd4c5bdc9
    `last_trigger_date` DATETIME NULL COMMENT 'Fineract source column last_trigger_date',
    -- column_id: ef96b990-c2a3-451d-bcba-b721905ba92e
    `recurrence_start_date` DATETIME NULL COMMENT 'Fineract source column recurrence_start_date',
    -- column_id: f678b9a5-e9a8-4518-b012-868e4da7bced
    `is_visible` BOOLEAN NULL COMMENT 'Fineract source column is_visible',
    -- column_id: 7e1b70cc-4c03-4edc-8d19-db7fd9cb1131
    `is_notification` BOOLEAN NULL COMMENT 'Fineract source column is_notification',
    -- column_id: 4cf9ba0a-7db7-4f04-870a-267830fb6c7d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
