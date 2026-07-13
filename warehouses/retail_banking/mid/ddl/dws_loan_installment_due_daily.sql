-- Reviewed aggregate from dwd_loan_installment
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_installment_due_daily;
-- table_id: b6fac060-9ce6-4f39-b16b-3ab021df3276
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_installment_due_daily (
    -- column_id: 21954698-e8a4-4478-ad53-ba4c43b869ce
    `stat_date` DATE NOT NULL COMMENT 'contractual_due_date',
    -- column_id: bc24d63d-b854-44eb-abfd-fdb0ca18373f
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 861589f5-36aa-4f11-9c64-a6cc2fb73475
    `installment_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: f3c60276-63c4-4ce5-b3f3-5c4ed796c174
    `scheduled_principal_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(principal_amount)',
    -- column_id: 15ca6dbf-1d13-4e96-b0de-c3ea4863df2b
    `scheduled_interest_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(interest_amount)',
    -- column_id: 6f2b0918-43de-406c-9701-edeab3bf742d
    `scheduled_fee_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(fee_charges_amount)',
    -- column_id: 593be445-7c6c-4279-bbe4-fa70fc763da4
    `scheduled_penalty_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(penalty_charges_amount)',
    -- column_id: 6c9ca9e0-e376-414f-8e33-0481316e239f
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
