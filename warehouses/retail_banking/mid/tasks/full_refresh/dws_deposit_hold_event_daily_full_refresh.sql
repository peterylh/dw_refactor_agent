SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_deposit_hold_event
TRUNCATE TABLE retail_banking_dm.dws_deposit_hold_event_daily;

INSERT INTO retail_banking_dm.dws_deposit_hold_event_daily (
    `stat_date`,
    `savings_account_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`savings_account_id` AS `savings_account_id`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_deposit_hold_event AS src
WHERE src.`transaction_date` IS NOT NULL
  AND (DATE(src.`transaction_date`) IS NULL OR (DATE(src.`transaction_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`transaction_date`) <= CAST(@etl_end_date AS DATE)))
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`savings_account_id`,
    src.`transaction_type_enum`;
