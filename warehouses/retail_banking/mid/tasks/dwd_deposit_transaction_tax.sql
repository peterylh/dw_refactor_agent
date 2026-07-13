-- Human-reviewed semantic target: retail_banking_dm.dwd_deposit_transaction_tax
TRUNCATE TABLE retail_banking_dm.dwd_deposit_transaction_tax;

INSERT INTO retail_banking_dm.dwd_deposit_transaction_tax (
    `id`,
    `savings_transaction_id`,
    `tax_component_id`,
    `amount`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`savings_transaction_id`,
    src.`tax_component_id`,
    src.`amount`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_savings_account_transaction_tax_details AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_savings_account_transaction AS date_parent
    ON src.`savings_transaction_id` = date_parent.`id`;
