SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_transaction
DELETE FROM retail_banking_dm.dwd_share_transaction
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_share_transaction
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_share_transaction (
    `id`,
    `account_id`,
    `transaction_date`,
    `total_shares`,
    `unit_price`,
    `amount`,
    `charge_amount`,
    `amount_paid`,
    `status_enum`,
    `type_enum`,
    `is_active`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`account_id`,
    src.`transaction_date`,
    src.`total_shares`,
    src.`unit_price`,
    src.`amount`,
    src.`charge_amount`,
    src.`amount_paid`,
    src.`status_enum`,
    src.`type_enum`,
    src.`is_active`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_account_transactions AS src
WHERE DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`transaction_date`) IS NULL;
