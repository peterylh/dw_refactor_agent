SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_transaction_repayment_schedule_mapping
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_repayment_allocation;
-- table_id: fc623d0b-e57e-48d7-8cc2-35983a3cb0f3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_repayment_allocation (
    -- column_id: 3b1f2909-e1c0-4195-9a02-802965245912
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 79f7d254-fedd-4f67-a940-54e0b07125f8
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: b21ddad2-bdb3-4cac-95c9-83130abfc41e
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 17ad1913-d5e4-469e-889b-6da005d8cf2e
    `loan_repayment_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_repayment_schedule_id',
    -- column_id: 15a26e2b-f364-4960-bfe9-7cdd499e03ab
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 4c571f2e-099c-4ef4-b79a-acbbc330c33c
    `principal_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_portion_derived',
    -- column_id: e0550246-7a13-460d-a771-72aefa0c309b
    `interest_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_portion_derived',
    -- column_id: 73b3ad5b-bb39-4124-921a-42ff4d983cb1
    `fee_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_portion_derived',
    -- column_id: 95f3d102-d5c9-4961-8d62-fb97fdfa6e8d
    `penalty_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_portion_derived',
    -- column_id: 841d757d-1973-40e9-8b65-eee26f49a10e
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
