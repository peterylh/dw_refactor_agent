-- ODS mirror of Apache Fineract scheduled_email_messages_outbound (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_scheduled_email_messages_outbound;
-- table_id: d24c48b4-a243-40e5-9cef-0207a7288bc8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_scheduled_email_messages_outbound (
    -- column_id: 274ca256-79d6-4cfe-a89d-642e7414f01c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b0eeae53-e288-4054-a175-e048271a0fbd
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: ecdb0afc-6398-4e9b-a63a-a0280e3271ba
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: a8a77518-08af-49e7-97d8-dea629025a3d
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 97aed8c9-3e2b-4aba-9516-f3878d486966
    `email_campaign_id` BIGINT NULL COMMENT 'Fineract source column email_campaign_id',
    -- column_id: 38ee0a12-bff1-49e5-a3ad-3c235e27fb8e
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 77098d7f-0dc0-477a-94ca-727a24f99c39
    `email_address` VARCHAR(50) NOT NULL COMMENT 'Fineract source column email_address',
    -- column_id: 9b4279db-267a-48c5-b190-aa5ddf6984b9
    `email_subject` VARCHAR(50) NOT NULL COMMENT 'Fineract source column email_subject',
    -- column_id: d10e6ba4-7663-477f-8d8f-b11c2c3fe7d0
    `message` STRING NOT NULL COMMENT 'Fineract source column message',
    -- column_id: 3ec9fbfa-861a-432f-b005-9b1cdf6d1ea7
    `campaign_name` VARCHAR(200) NULL COMMENT 'Fineract source column campaign_name',
    -- column_id: e45f4613-0bf4-4f00-924c-ea4ea766321b
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: bd842849-a48b-4b94-8404-b79bd13a2099
    `error_message` STRING NULL COMMENT 'Fineract source column error_message',
    -- column_id: fbab27ee-0c95-4bc6-93f7-4b4de37427d4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
