-- Human-reviewed aggregation from dwd_office_cash_transfer
TRUNCATE TABLE retail_banking_dm.dws_office_cash_transfer_daily;

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
GROUP BY
    DATE(src.`transaction_date`),
    src.`from_office_id`,
    src.`to_office_id`,
    src.`currency_code`;
