SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_deposit_hold_event
TRUNCATE TABLE retail_banking_dm.dwd_deposit_hold_event;

INSERT INTO retail_banking_dm.dwd_deposit_hold_event (
    `id`,
    `savings_account_id`,
    `amount`,
    `transaction_type_enum`,
    `transaction_date`,
    `is_reversed`,
    `created_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`savings_account_id`,
    src.`amount`,
    src.`transaction_type_enum`,
    src.`transaction_date`,
    src.`is_reversed`,
    src.`created_date`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_deposit_account_on_hold_transaction AS src;
