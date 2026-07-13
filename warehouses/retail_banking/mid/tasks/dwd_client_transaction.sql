SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_client_transaction
DELETE FROM retail_banking_dm.dwd_client_transaction
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_client_transaction
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_client_transaction (
    `id`,
    `client_id`,
    `office_id`,
    `currency_code`,
    `payment_detail_id`,
    `is_reversed`,
    `external_id`,
    `transaction_date`,
    `transaction_type_enum`,
    `amount`,
    `created_date`,
    `created_on_utc`,
    `created_by`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `submitted_on_date`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`office_id`,
    src.`currency_code`,
    src.`payment_detail_id`,
    src.`is_reversed`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`transaction_date`,
    src.`transaction_type_enum`,
    src.`amount`,
    src.`created_date`,
    src.`created_on_utc`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`submitted_on_date`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_transaction AS src
WHERE DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`transaction_date`) IS NULL;
