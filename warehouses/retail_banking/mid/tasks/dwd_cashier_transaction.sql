-- Human-reviewed semantic target: retail_banking_dm.dwd_cashier_transaction
TRUNCATE TABLE retail_banking_dm.dwd_cashier_transaction;

INSERT INTO retail_banking_dm.dwd_cashier_transaction (
    `id`,
    `cashier_id`,
    `txn_type`,
    `txn_amount`,
    `txn_date`,
    `created_date`,
    `entity_type`,
    `entity_id`,
    `txn_note`,
    `currency_code`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`cashier_id`,
    src.`txn_type`,
    src.`txn_amount`,
    src.`txn_date`,
    src.`created_date`,
    src.`entity_type`,
    src.`entity_id`,
    src.`txn_note`,
    src.`currency_code`,
    DATE(src.`txn_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_cashier_transactions AS src;
