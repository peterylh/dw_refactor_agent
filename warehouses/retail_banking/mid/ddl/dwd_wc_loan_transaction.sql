-- DWD generated from m_wc_loan_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_wc_loan_transaction;
-- table_id: d52e5024-97bd-4376-b865-46363a115695
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_wc_loan_transaction (
    -- column_id: 917d3c7a-b8ae-49b3-874c-db574c48fcb1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bd96142e-bdf9-48fa-ae84-99d57f4f8839
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: e4f1272a-105f-48c0-86ed-1b8f5a39f0a1
    `payment_detail_id` BIGINT NULL COMMENT 'Fineract source column payment_detail_id',
    -- column_id: b1f91f86-6779-4781-b2f1-6692a537c601
    `classification_cv_id` INT NULL COMMENT 'Fineract source column classification_cv_id',
    -- column_id: d3f4bc21-5255-4347-bc7c-9d495d40515f
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: f283ad39-ba85-482e-a181-e18d8349b2b3
    `transaction_type_id` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_id',
    -- column_id: 701cee01-ba79-4f62-8a9b-783b4f823b15
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 6ace6b94-c4cc-46a7-b678-5e4f7dc61b52
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 164940e9-2884-4f75-9b2c-3d2086603eba
    `transaction_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column transaction_amount',
    -- column_id: 874d0cca-a3e7-475a-a7de-7cc18a365307
    `version` SMALLINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 6a99a8c8-fccc-4e7e-a45b-c21342c124ce
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 97128418-c200-4f3a-b635-144b80076fee
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8fc4caab-31a6-4337-9beb-b30fc911c778
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: fb5b4e30-72fc-41a0-9132-a87822cc1c62
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: ee2d6e8d-631a-474f-b01e-f7df7bcc5dea
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 46f57c2d-c21c-4959-ac78-0908d79d42cf
    `reversal_external_id` VARCHAR(64) NULL COMMENT 'Fineract source column reversal_external_id',
    -- column_id: 745c8743-534a-4f83-ab39-78e6ce1b8889
    `reversed_on_date` DATE NULL COMMENT 'Fineract source column reversed_on_date',
    -- column_id: 050d8111-97bf-48ba-a42e-2ef1e63b604e
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: d0653c3e-34b6-43e3-a9bf-493ec0364ebf
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
