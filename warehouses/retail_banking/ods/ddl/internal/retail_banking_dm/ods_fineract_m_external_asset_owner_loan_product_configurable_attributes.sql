-- ODS mirror of Apache Fineract m_external_asset_owner_loan_product_configurable_attributes (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_loan_product_configurable_attributes;
-- table_id: ebe5513a-e9eb-4d22-8a49-38c76393c8bc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_loan_product_configurable_attributes (
    -- column_id: bdd44d87-324c-47ad-9a59-0e51721a78ba
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 17a30a56-732a-4567-a343-b4897daf88eb
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: 43ac32b4-82d3-4619-b620-cb5fbc992aaf
    `attribute_key` VARCHAR(255) NOT NULL COMMENT 'Fineract source column attribute_key',
    -- column_id: 3237fc95-44e5-43be-b639-3a379cadd52c
    `attribute_value` VARCHAR(255) NOT NULL COMMENT 'Fineract source column attribute_value',
    -- column_id: 4fdb72ef-9940-42b6-adcb-74d9c405675a
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 13c38872-03d2-4e67-9bb7-7e14bdb87d3c
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 65d57ca3-73f9-4d96-9087-40acb09d5760
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 98498769-83b6-4db2-8455-b08376f8e47d
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: e8c1a0bb-dc15-4df1-997f-7d658d14c0ae
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
