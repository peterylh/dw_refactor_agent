SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_client_transaction
DELETE FROM retail_banking_dm.dws_client_transaction_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_client_transaction_daily (
    `stat_date`,
    `office_id`,
    `client_id`,
    `currency_code`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`client_id` AS `client_id`,
    src.`currency_code` AS `currency_code`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_client_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`office_id`,
    src.`client_id`,
    src.`currency_code`,
    src.`transaction_type_enum`;
