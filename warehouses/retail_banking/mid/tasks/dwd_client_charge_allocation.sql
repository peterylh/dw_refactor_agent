-- Human-reviewed semantic target: retail_banking_dm.dwd_client_charge_allocation
TRUNCATE TABLE retail_banking_dm.dwd_client_charge_allocation;

INSERT INTO retail_banking_dm.dwd_client_charge_allocation (
    `id`,
    `client_transaction_id`,
    `client_charge_id`,
    `amount`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_transaction_id`,
    src.`client_charge_id`,
    src.`amount`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_charge_paid_by AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_client_transaction AS date_parent
    ON src.`client_transaction_id` = date_parent.`id`;
