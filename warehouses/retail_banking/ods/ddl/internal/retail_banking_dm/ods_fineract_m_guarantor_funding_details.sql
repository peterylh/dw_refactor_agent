-- ODS mirror of Apache Fineract m_guarantor_funding_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_guarantor_funding_details;
-- table_id: 278fbfab-fe99-4a37-b689-de688e9054fe
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_guarantor_funding_details (
    -- column_id: 639b2dee-ceaa-4c7e-9b44-0ff3c900f7c7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 70c4ab6a-3ebd-476f-a06d-47c566a371bd
    `guarantor_id` BIGINT NOT NULL COMMENT 'Fineract source column guarantor_id',
    -- column_id: 3760cc30-8304-42d7-9904-f112e04fb8cf
    `account_associations_id` BIGINT NOT NULL COMMENT 'Fineract source column account_associations_id',
    -- column_id: 8a824649-07e6-4f25-9e10-350369ae881c
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 2cd1aca4-6400-41e6-a785-d1e48e986711
    `amount_released_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_released_derived',
    -- column_id: 4ceb0ea9-4622-4cea-ba1a-0c11e69495e3
    `amount_remaining_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_remaining_derived',
    -- column_id: f3630107-0ff3-4433-a6be-3fdb9a1f4461
    `amount_transfered_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_transfered_derived',
    -- column_id: 92d20da4-807d-41c1-afbd-aceae8a4f804
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 2d0580ae-fb3a-456a-b62c-9b6a9751535d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
