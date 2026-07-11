-- Human-reviewed aggregation from dwd_loan_installment_charge
TRUNCATE TABLE retail_banking_dm.dws_loan_installment_charge_due_current;

INSERT INTO retail_banking_dm.dws_loan_installment_charge_due_current (
    `due_date`,
    `loan_id`,
    `loan_charge_id`,
    `installment_charge_count`,
    `total_due_amount`,
    `current_paid_amount`,
    `current_waived_amount`,
    `current_written_off_amount`,
    `current_outstanding_amount`,
    `etl_time`
)
SELECT
    DATE(src.`due_date`) AS `due_date`,
    src.`loan_id` AS `loan_id`,
    src.`loan_charge_id` AS `loan_charge_id`,
    COUNT(*) AS `installment_charge_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_due_amount`,
    COALESCE(SUM(src.`amount_paid_derived`), 0) AS `current_paid_amount`,
    COALESCE(SUM(src.`amount_waived_derived`), 0) AS `current_waived_amount`,
    COALESCE(SUM(src.`amount_writtenoff_derived`), 0) AS `current_written_off_amount`,
    COALESCE(SUM(src.`amount_outstanding_derived`), 0) AS `current_outstanding_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_installment_charge AS src
WHERE src.`due_date` IS NOT NULL
GROUP BY
    DATE(src.`due_date`),
    src.`loan_id`,
    src.`loan_charge_id`;
