SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.dws_cashier_transaction_daily
TRUNCATE TABLE retail_banking_dm.ads_cashier_operation_daily;

INSERT INTO retail_banking_dm.ads_cashier_operation_daily (
    `stat_date`,
    `cashier_id`,
    `currency_code`,
    `txn_type`,
    `record_count`,
    `total_txn_amount`,
    `average_txn_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`cashier_id`,
    src.`currency_code`,
    src.`txn_type`,
    src.`record_count` AS `record_count`,
    src.`total_txn_amount` AS `total_txn_amount`,
    (src.`total_txn_amount`) / nullif((src.`record_count`), 0) AS `average_txn_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_cashier_transaction_daily AS src
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)));
