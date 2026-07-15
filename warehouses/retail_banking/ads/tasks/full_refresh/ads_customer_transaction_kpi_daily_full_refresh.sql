SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.stage_client_transaction_daily
TRUNCATE TABLE retail_banking_dm.ads_customer_transaction_kpi_daily;

INSERT INTO retail_banking_dm.ads_customer_transaction_kpi_daily (
    `stat_date`,
    `office_id`,
    `client_id`,
    `currency_code`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `average_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`office_id`,
    src.`client_id`,
    src.`currency_code`,
    src.`transaction_type_enum`,
    src.`record_count` AS `record_count`,
    src.`total_amount` AS `total_amount`,
    (src.`total_amount`) / nullif((src.`record_count`), 0) AS `average_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.stage_client_transaction_daily AS src
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)));
