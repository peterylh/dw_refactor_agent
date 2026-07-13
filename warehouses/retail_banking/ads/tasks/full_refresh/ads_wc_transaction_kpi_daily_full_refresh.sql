SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.dws_wc_loan_transaction_daily
TRUNCATE TABLE retail_banking_dm.ads_wc_transaction_kpi_daily;

INSERT INTO retail_banking_dm.ads_wc_transaction_kpi_daily (
    `stat_date`,
    `wc_loan_id`,
    `transaction_type_id`,
    `record_count`,
    `total_transaction_amount`,
    `average_transaction_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`wc_loan_id`,
    src.`transaction_type_id`,
    src.`record_count` AS `record_count`,
    src.`total_transaction_amount` AS `total_transaction_amount`,
    (src.`total_transaction_amount`) / nullif((src.`record_count`), 0) AS `average_transaction_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_wc_loan_transaction_daily AS src
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)));
