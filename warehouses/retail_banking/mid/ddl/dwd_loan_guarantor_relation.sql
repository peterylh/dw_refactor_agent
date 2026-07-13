-- DWD generated from m_guarantor
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_guarantor_relation;
-- table_id: b2b96878-aebd-4ae5-ace3-4c322f93265c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_guarantor_relation (
    -- column_id: 20d494dc-1dc3-4181-80dd-66be0d8f25fb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1db257bc-4329-40a3-99dd-514dd0ab91e0
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 4dee9f6b-fdae-46ca-b0f2-eefa70540691
    `client_reln_cv_id` INT NULL COMMENT 'Fineract source column client_reln_cv_id',
    -- column_id: a8a044f5-01bc-4d99-adf1-37c109f52bfd
    `type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: 025da093-ac88-4777-847f-6b44b5c52b19
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: 552321df-585a-4ca0-9b38-3da023e446d3
    `firstname` VARCHAR(256) NULL COMMENT 'Fineract source column firstname',
    -- column_id: faa44170-41b9-4461-938b-7fddd8416f96
    `lastname` VARCHAR(256) NULL COMMENT 'Fineract source column lastname',
    -- column_id: f9a6621a-9517-444b-9e8e-8e37e7b63746
    `dob` VARCHAR(256) NULL COMMENT 'Fineract source column dob',
    -- column_id: d2419389-093b-4b1a-8dc1-a676d31ecb9c
    `address_line_1` VARCHAR(256) NULL COMMENT 'Fineract source column address_line_1',
    -- column_id: c39cbe21-7033-4af6-89e9-30f720160f87
    `address_line_2` VARCHAR(256) NULL COMMENT 'Fineract source column address_line_2',
    -- column_id: 763bbc0e-f376-4a2b-9753-f4c8272c363e
    `city` VARCHAR(256) NULL COMMENT 'Fineract source column city',
    -- column_id: 822836f0-7543-4dbb-9e5d-6e2cb063e30c
    `state` VARCHAR(50) NULL COMMENT 'Fineract source column state',
    -- column_id: e49241f9-9063-4604-8aa5-aa0de4388abf
    `country` VARCHAR(50) NULL COMMENT 'Fineract source column country',
    -- column_id: 73fde55b-d13b-4df2-acf8-5ec3bcc63696
    `zip` VARCHAR(256) NULL COMMENT 'Fineract source column zip',
    -- column_id: 2eba00ad-1cbf-4e34-b212-80cc755b25c1
    `house_phone_number` VARCHAR(64) NULL COMMENT 'Fineract source column house_phone_number',
    -- column_id: de3b9f6b-1b3f-4ac1-aaeb-b815c0a3fcc6
    `mobile_number` VARCHAR(64) NULL COMMENT 'Fineract source column mobile_number',
    -- column_id: aecb993d-9edf-445d-a515-835aa6bb0aff
    `comment` VARCHAR(256) NULL COMMENT 'Fineract source column comment',
    -- column_id: fcfa51fd-dfc9-496a-8e48-f1de2a01a942
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 0fd6d916-5b67-45a9-ac53-c7d7e05be77d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
