-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_collateral_pledge
TRUNCATE TABLE retail_banking_dm.dwd_loan_collateral_pledge;

INSERT INTO retail_banking_dm.dwd_loan_collateral_pledge (
    `id`,
    `quantity`,
    `loan_id`,
    `client_collateral_id`,
    `is_released`,
    `transaction_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`quantity`,
    src.`loan_id`,
    src.`client_collateral_id`,
    src.`is_released`,
    src.`transaction_id`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_collateral_management AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_transaction AS date_parent
    ON src.`transaction_id` = date_parent.`id`;
