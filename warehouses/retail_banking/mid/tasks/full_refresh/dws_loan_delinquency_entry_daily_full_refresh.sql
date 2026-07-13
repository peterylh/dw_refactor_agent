SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_loan_delinquency_event
TRUNCATE TABLE retail_banking_dm.dws_loan_delinquency_entry_daily;

INSERT INTO retail_banking_dm.dws_loan_delinquency_entry_daily (
    `stat_date`,
    `loan_id`,
    `delinquency_range_id`,
    `entry_count`,
    `etl_time`
)
SELECT
    DATE(src.`addedon_date`) AS `stat_date`,
    src.`loan_id` AS `loan_id`,
    src.`delinquency_range_id` AS `delinquency_range_id`,
    COUNT(*) AS `entry_count`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_delinquency_event AS src
WHERE src.`addedon_date` IS NOT NULL
  AND (DATE(src.`addedon_date`) IS NULL OR (DATE(src.`addedon_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`addedon_date`) <= CAST(@etl_end_date AS DATE)))
GROUP BY
    DATE(src.`addedon_date`),
    src.`loan_id`,
    src.`delinquency_range_id`;
