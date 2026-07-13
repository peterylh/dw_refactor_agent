SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_office_cash_transfer
DELETE FROM retail_banking_dm.dws_office_cash_transfer_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_office_cash_transfer_daily (
    `stat_date`,
    `from_office_id`,
    `to_office_id`,
    `currency_code`,
    `record_count`,
    `total_transaction_amount`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`from_office_id` AS `from_office_id`,
    src.`to_office_id` AS `to_office_id`,
    src.`currency_code` AS `currency_code`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`transaction_amount`), 0) AS `total_transaction_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_office_cash_transfer AS src
WHERE src.`transaction_date` IS NOT NULL
  AND DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`transaction_date`),
    src.`from_office_id`,
    src.`to_office_id`,
    src.`currency_code`;
