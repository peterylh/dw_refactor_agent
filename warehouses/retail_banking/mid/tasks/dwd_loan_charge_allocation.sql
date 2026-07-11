SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_charge_allocation
TRUNCATE TABLE retail_banking_dm.dwd_loan_charge_allocation;

INSERT INTO retail_banking_dm.dwd_loan_charge_allocation (
    `id`,
    `loan_transaction_id`,
    `loan_charge_id`,
    `amount`,
    `installment_number`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_transaction_id`,
    src.`loan_charge_id`,
    src.`amount`,
    src.`installment_number`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_charge_paid_by AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_transaction AS date_parent
    ON src.`loan_transaction_id` = date_parent.`id`;
