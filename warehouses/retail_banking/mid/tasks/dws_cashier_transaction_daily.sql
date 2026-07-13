SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_cashier_transaction
DELETE FROM retail_banking_dm.dws_cashier_transaction_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_cashier_transaction_daily (
    `stat_date`,
    `cashier_id`,
    `currency_code`,
    `txn_type`,
    `record_count`,
    `total_txn_amount`,
    `etl_time`
)
SELECT
    DATE(src.`txn_date`) AS `stat_date`,
    src.`cashier_id` AS `cashier_id`,
    src.`currency_code` AS `currency_code`,
    src.`txn_type` AS `txn_type`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`txn_amount`), 0) AS `total_txn_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_cashier_transaction AS src
WHERE src.`txn_date` IS NOT NULL
  AND DATE(src.`txn_date`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`txn_date`),
    src.`cashier_id`,
    src.`currency_code`,
    src.`txn_type`;
