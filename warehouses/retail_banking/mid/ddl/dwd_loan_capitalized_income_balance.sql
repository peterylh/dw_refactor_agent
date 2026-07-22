SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_capitalized_income_balance
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_capitalized_income_balance;
-- table_id: ccf218e1-f616-4116-8954-3575816d5391
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_capitalized_income_balance (
    -- column_id: 823ad789-fd9c-443e-9faa-bf21b8501fb6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d4dae9a9-3630-4a83-abd2-5b1a25f6c29f
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 3c295a6b-b120-4a54-8f30-6fea2ecabe27
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 985f5946-f5c7-4cbc-a375-ae567e62d044
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: cb619b75-e6e6-4c6a-a55a-511128fb604a
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: d3f689c1-5915-4e83-bb6e-0e5a49ae7f93
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 0fe042ca-14d0-4ac8-9e7c-0b6cc7d35e3e
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: 112bca32-0e38-468f-bc7e-043f28059f9f
    `unrecognized_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column unrecognized_amount',
    -- column_id: da6ba03c-9e53-4604-96cc-d5172bcb9bd6
    `charged_off_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column charged_off_amount',
    -- column_id: 594c3959-d282-4766-b79d-3b2e2144918b
    `amount_adjustment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_adjustment',
    -- column_id: f60c3cca-ce97-45e6-a4e3-47291ebea5a6
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 6300333c-c9e5-4fee-8a7b-aab79d7c1eea
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 47aba6e9-284a-4ccd-8157-bf2b81f67b0b
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 1ab39923-e8a0-426b-ad5c-3173ccb1892f
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 4b5836cf-4e86-45db-9b3c-728764034d13
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 01ba0873-9931-4350-b1b9-d4d346123f1b
    `is_closed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_closed',
    -- column_id: fc523433-7de1-4764-b2fe-af6471d49d89
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
