-- DWD generated from m_loan_buy_down_fee_balance
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_buy_down_fee_balance;
-- table_id: f9fa7b48-70fb-4d17-a35a-be427d78b232
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_buy_down_fee_balance (
    -- column_id: 5753c749-2059-4bf5-89b2-b7bb63459c45
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7490e093-2d15-4bf8-afab-9263db80d435
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 1117196c-25d4-4706-8430-6fdfac3e66ca
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 1978565a-b04f-481b-8c1b-afa3a7415034
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 1b7cf9b2-c1ea-4a98-9316-77d374723519
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: b2330984-6cf7-4b3c-bed4-f8e51fce81c1
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: 32ddb8aa-58ef-4c44-aac2-6b7426e54431
    `unrecognized_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column unrecognized_amount',
    -- column_id: 5373bbe1-11d1-46c7-9c2c-a9d9f4e71183
    `charged_off_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column charged_off_amount',
    -- column_id: 0d3d05ed-8406-4b35-b30a-d41faf130f0e
    `amount_adjustment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_adjustment',
    -- column_id: afb37992-359e-4197-84f6-3337bc85c871
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7ba39d8b-6c88-4494-ad1c-881c5ed4ae21
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 0cfc146c-40a8-486f-b310-12060bdc7e91
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 175f9565-db2b-4a96-84e5-e18e9a1da4d4
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: a73716c4-7a12-4bff-a038-ea925d06e755
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: d1e1db50-9cf8-4110-971b-1d0c4cced694
    `is_closed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_closed',
    -- column_id: 10daa411-ce28-4984-9c1a-8a8b12e58801
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: f876ba08-1e1c-4393-9994-995ab9502e2e
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
