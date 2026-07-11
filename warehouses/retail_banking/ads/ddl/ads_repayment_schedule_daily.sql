-- Reviewed application metrics derived from dws_loan_installment_due_daily
DROP TABLE IF EXISTS retail_banking_dm.ads_repayment_schedule_daily;
-- table_id: 3e28b0bb-39aa-45cd-bed1-ebeb9d7331f9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ads_repayment_schedule_daily (
    -- column_id: f8fbef3f-9675-4d86-8bc2-0fcb375ff55a
    `stat_date` DATE NOT NULL COMMENT 'contractual_due_date',
    -- column_id: 15539b59-c939-42ac-8dc1-f99f8917c0ea
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b620d227-9892-40d3-a46d-867c0e796d30
    `installment_count` BIGINT NULL COMMENT 'derived metric: source.installment_count',
    -- column_id: 8974bf35-83a6-4366-a60c-7d45304aac28
    `scheduled_total_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: scheduled_principal_amount + scheduled_interest_amount + scheduled_fee_amount + scheduled_penalty_amount',
    -- column_id: d5ddffc3-d2bb-4df1-b9a4-9b1319d05bda
    `average_scheduled_amount` DECIMAL(38,6) NULL COMMENT 'calculated metric: scheduled_total_amount / nullif(installment_count, 0)',
    -- column_id: 4e833cc8-1d1b-4f36-b33f-801d81ad83b0
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`stat_date`, `loan_id`)
DISTRIBUTED BY HASH(`stat_date`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
