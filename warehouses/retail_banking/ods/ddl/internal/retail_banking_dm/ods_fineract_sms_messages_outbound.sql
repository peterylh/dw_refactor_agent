-- ODS mirror of Apache Fineract sms_messages_outbound (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_sms_messages_outbound;
-- table_id: 9afaf40f-3d3e-4995-993f-6a3d8aa21ecb
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_sms_messages_outbound (
    -- column_id: 5e98f71d-c63b-47bc-a863-a661c0f1fb9f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ca98552e-2706-4bc6-8098-d37587f1c28d
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 1383c9e6-591b-49c4-b4a6-3da1b617a2a3
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 69ec9e55-aa9a-4b5d-ba4e-7c26a5d12067
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 0944004b-7fda-49ff-be9a-e1488ddf3914
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 1c7e50a8-23b5-47a3-84b5-7c74705e9ad7
    `mobile_no` VARCHAR(50) NULL COMMENT 'Fineract source column mobile_no',
    -- column_id: 37ec4b62-c3af-442d-baca-06568a5ea724
    `message` VARCHAR(1000) NOT NULL COMMENT 'Fineract source column message',
    -- column_id: 51534ebe-b2b4-478a-a533-21f59d295dc2
    `campaign_id` BIGINT NULL COMMENT 'Fineract source column campaign_id',
    -- column_id: 03470841-8ac8-461f-ad44-137deede2b2a
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: bc8dedcf-03b7-43ea-bcd4-ba3d439ce4e2
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 0375e222-dc6e-432d-b4b6-a24714de6114
    `delivered_on_date` DATETIME NULL COMMENT 'Fineract source column delivered_on_date',
    -- column_id: 28b1d076-53a4-458f-be8f-eafef32a8bb5
    `is_notification` BOOLEAN NOT NULL COMMENT 'Fineract source column is_notification',
    -- column_id: a46620e1-c122-4b0f-a463-3e944f9f7755
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
