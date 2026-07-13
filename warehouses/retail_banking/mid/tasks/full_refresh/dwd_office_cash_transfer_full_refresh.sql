SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_office_cash_transfer
TRUNCATE TABLE retail_banking_dm.dwd_office_cash_transfer;

INSERT INTO retail_banking_dm.dwd_office_cash_transfer (
    `id`,
    `from_office_id`,
    `to_office_id`,
    `currency_code`,
    `currency_digits`,
    `transaction_amount`,
    `transaction_date`,
    `description`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`from_office_id`,
    src.`to_office_id`,
    src.`currency_code`,
    src.`currency_digits`,
    src.`transaction_amount`,
    src.`transaction_date`,
    src.`description`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_office_transaction AS src
WHERE (DATE(src.`transaction_date`) IS NULL OR (DATE(src.`transaction_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`transaction_date`) <= CAST(@etl_end_date AS DATE)));
