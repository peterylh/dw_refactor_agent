SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.bridge_guarantee_transaction
TRUNCATE TABLE retail_banking_dm.bridge_guarantee_transaction;

INSERT INTO retail_banking_dm.bridge_guarantee_transaction (
    `id`,
    `guarantor_fund_detail_id`,
    `loan_transaction_id`,
    `deposit_on_hold_transaction_id`,
    `is_reversed`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`guarantor_fund_detail_id`,
    src.`loan_transaction_id`,
    src.`deposit_on_hold_transaction_id`,
    src.`is_reversed`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_guarantor_transaction AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_transaction AS date_parent
    ON src.`loan_transaction_id` = date_parent.`id`
WHERE (DATE(date_parent.`transaction_date`) IS NULL OR (DATE(date_parent.`transaction_date`) >= CAST(@etl_start_date AS DATE) AND DATE(date_parent.`transaction_date`) <= CAST(@etl_end_date AS DATE)));
