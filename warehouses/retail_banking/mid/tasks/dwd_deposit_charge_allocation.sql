SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_deposit_charge_allocation
TRUNCATE TABLE retail_banking_dm.dwd_deposit_charge_allocation;

INSERT INTO retail_banking_dm.dwd_deposit_charge_allocation (
    `id`,
    `savings_account_transaction_id`,
    `savings_account_charge_id`,
    `amount`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`savings_account_transaction_id`,
    src.`savings_account_charge_id`,
    src.`amount`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_savings_account_charge_paid_by AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_savings_account_transaction AS date_parent
    ON src.`savings_account_transaction_id` = date_parent.`id`;
