-- ODS mirror of Apache Fineract m_external_asset_owner_transfer_loan_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_loan_mapping;
-- table_id: 9593cbfa-d6b3-4893-ad87-ae1b9598d336
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_loan_mapping (
    -- column_id: 8c4dc346-e84b-4885-97ca-b3a42b064c80
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: d3488952-ad2f-4a25-b9e3-f10fb8f95017
    `loan_id` BIGINT NOT NULL COMMENT 'Loan ID',
    -- column_id: 678293c2-e8e1-43a4-9e49-37040adaebee
    `owner_transfer_id` BIGINT NOT NULL COMMENT 'Owner',
    -- column_id: 586e69d6-42ec-4f6b-847e-debf05d6c276
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7bda7793-055a-4710-9065-38574e0fd781
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: cd4a73e9-5812-495a-8364-647ce5dfae11
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: ec1adb44-2d9a-41db-af3b-3485ceb0e417
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 53c475eb-8437-4807-adf5-5fa5db94c002
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
