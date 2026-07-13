-- Reviewed aggregate from dwd_loan_transaction
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_transaction_daily;
-- table_id: 48ec0011-5c01-418c-b6ec-419a783cc2e4
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_transaction_daily (
    -- column_id: f6cff91d-89af-430d-b5c2-d85edd66a3ed
    `stat_date` DATE NOT NULL COMMENT 'event_date',
    -- column_id: 92203c08-3bb9-441c-88d2-9a89d6b0ac3c
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: d4674b1c-ce86-45d9-9047-81716f191ffe
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 10596665-15ee-4bd9-8929-452d214581d1
    `transaction_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column transaction_type_enum',
    -- column_id: 8568b7d6-8da6-4e24-9c78-4b2acc7c81ca
    `record_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 5fe0c4ba-2a20-4275-93a6-b92d4e4db08d
    `total_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: be69cb4f-6028-40b5-8837-9d0fd342b105
    `total_principal_component` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(principal_portion_derived)',
    -- column_id: 94e67633-97b6-4672-aae2-8eec569c82ef
    `total_interest_component` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(interest_portion_derived)',
    -- column_id: e5854a7d-ecbb-46e8-abc9-f9e4236db4c6
    `total_fee_component` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(fee_charges_portion_derived)',
    -- column_id: a736498e-c329-4195-a098-8a184df36eb7
    `total_penalty_component` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(penalty_charges_portion_derived)',
    -- column_id: 0990af72-20ed-447f-a651-be49b2f2da7a
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `office_id`, `loan_id`, `transaction_type_enum`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
