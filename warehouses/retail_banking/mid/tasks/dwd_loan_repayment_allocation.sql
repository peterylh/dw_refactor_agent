SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_repayment_allocation
DELETE FROM retail_banking_dm.dwd_loan_repayment_allocation
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_repayment_allocation
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_loan_repayment_allocation (
    `id`,
    `loan_transaction_id`,
    `loan_repayment_schedule_id`,
    `amount`,
    `principal_portion_derived`,
    `interest_portion_derived`,
    `fee_charges_portion_derived`,
    `penalty_charges_portion_derived`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_transaction_id`,
    src.`loan_repayment_schedule_id`,
    src.`amount`,
    src.`principal_portion_derived`,
    src.`interest_portion_derived`,
    src.`fee_charges_portion_derived`,
    src.`penalty_charges_portion_derived`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_transaction_repayment_schedule_mapping AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_transaction AS date_parent
    ON src.`loan_transaction_id` = date_parent.`id`
WHERE DATE(date_parent.`transaction_date`) = CAST(@etl_date AS DATE)
   OR DATE(date_parent.`transaction_date`) IS NULL;
