-- Reviewed aggregate from dwd_loan_installment_charge
DROP TABLE IF EXISTS retail_banking_dm.dws_loan_installment_charge_due_current;
-- table_id: 34b0eb44-256d-4afb-89e1-0902a0b5a56c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dws_loan_installment_charge_due_current (
    -- column_id: e6c28ea8-e454-405e-b315-351d1bc4a443
    `due_date` DATE NOT NULL COMMENT 'contractual_due_date_not_snapshot_date',
    -- column_id: db9bd99d-bab9-4178-be17-d07673570020
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 58ab33d7-506d-4bab-b768-17fb6aef169f
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: b21d253f-63b4-4ad7-9001-50f6021e93a8
    `installment_charge_count` BIGINT NOT NULL COMMENT 'derived metric: count(*)',
    -- column_id: 428ee58f-32e0-489d-8acf-1673fb94db19
    `total_due_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount)',
    -- column_id: eb5126d8-95d2-415f-9814-efb7c2435c2a
    `current_paid_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount_paid_derived)',
    -- column_id: 11b99c0b-3e35-413a-a3bd-e2ef3bfafc45
    `current_waived_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount_waived_derived)',
    -- column_id: 04f82146-d587-441c-8554-a80df20cc0ce
    `current_written_off_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount_writtenoff_derived)',
    -- column_id: 59a4bd97-5db8-47cf-b927-1ca41dbc27a6
    `current_outstanding_amount` DECIMAL(38,6) NOT NULL COMMENT 'derived metric: sum(amount_outstanding_derived)',
    -- column_id: 425767b1-c117-40dc-803f-0c5de9112fe0
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`due_date`, `loan_id`, `loan_charge_id`)
AUTO PARTITION BY LIST (`due_date`) ()
DISTRIBUTED BY HASH(`due_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
