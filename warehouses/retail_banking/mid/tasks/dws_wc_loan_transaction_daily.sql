SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_wc_loan_transaction
DELETE FROM retail_banking_dm.dws_wc_loan_transaction_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_wc_loan_transaction_daily (
    `stat_date`,
    `wc_loan_id`,
    `transaction_type_id`,
    `record_count`,
    `total_transaction_amount`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`wc_loan_id` AS `wc_loan_id`,
    src.`transaction_type_id` AS `transaction_type_id`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`transaction_amount`), 0) AS `total_transaction_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_wc_loan_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`wc_loan_id`,
    src.`transaction_type_id`;
