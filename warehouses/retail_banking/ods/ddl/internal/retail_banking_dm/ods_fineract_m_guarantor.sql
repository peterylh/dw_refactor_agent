-- ODS mirror of Apache Fineract m_guarantor (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_guarantor;
-- table_id: 1d6ae996-7c83-429a-a4cf-bc360adc73f0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_guarantor (
    -- column_id: 0b3634c2-f657-407c-8287-f0ac9cc0dd35
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c93ca1b8-4b99-48bf-bce7-a27776464f68
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 5a100185-0159-4747-bff1-65842af78b4c
    `client_reln_cv_id` INT NULL COMMENT 'Fineract source column client_reln_cv_id',
    -- column_id: 4663b12d-be85-46e8-b550-7538e816b57a
    `type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: a2067c44-4ea6-4891-ac5c-287824f115c1
    `entity_id` BIGINT NULL COMMENT 'Fineract source column entity_id',
    -- column_id: 2ca31624-237f-4d60-aea7-0fd9e55f0fd2
    `firstname` VARCHAR(50) NULL COMMENT 'Fineract source column firstname',
    -- column_id: 571c9200-aa45-4476-9125-46d4dc3e185a
    `lastname` VARCHAR(50) NULL COMMENT 'Fineract source column lastname',
    -- column_id: 5882d220-0742-4147-a885-3917f77ace0a
    `dob` DATE NULL COMMENT 'Fineract source column dob',
    -- column_id: 16af030a-4125-4f0e-80f6-5e0fd3f4c896
    `address_line_1` VARCHAR(500) NULL COMMENT 'Fineract source column address_line_1',
    -- column_id: 9e7f4321-2b27-4bf3-bec1-c0dc81eb3eb0
    `address_line_2` VARCHAR(500) NULL COMMENT 'Fineract source column address_line_2',
    -- column_id: 5076a078-cf4f-4685-ae33-30bbb1c2995b
    `city` VARCHAR(50) NULL COMMENT 'Fineract source column city',
    -- column_id: 664adc75-267c-4665-9d88-b3d99a297c38
    `state` VARCHAR(50) NULL COMMENT 'Fineract source column state',
    -- column_id: 84ead157-0f19-421e-83db-6ca5da634876
    `country` VARCHAR(50) NULL COMMENT 'Fineract source column country',
    -- column_id: f41970c0-b26a-43ad-9947-7ded5ffe50a1
    `zip` VARCHAR(20) NULL COMMENT 'Fineract source column zip',
    -- column_id: bf0c28e5-6519-4e2f-a52c-05ddb3e7340c
    `house_phone_number` VARCHAR(20) NULL COMMENT 'Fineract source column house_phone_number',
    -- column_id: ff7b2d06-7320-49b9-a25d-2684eaba16fd
    `mobile_number` VARCHAR(20) NULL COMMENT 'Fineract source column mobile_number',
    -- column_id: b8db359c-806d-4854-a972-7cd4642806c2
    `comment` VARCHAR(500) NULL COMMENT 'Fineract source column comment',
    -- column_id: d173b0d0-3ca1-41a9-80f9-b6bb81359119
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: de108b57-5135-4b49-b58b-1bb52d906821
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
