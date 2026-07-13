SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_collection_action
TRUNCATE TABLE retail_banking_dm.dws_collection_action_daily;

INSERT INTO retail_banking_dm.dws_collection_action_daily (
    `stat_date`,
    `loan_id`,
    `action`,
    `record_count`,
    `etl_time`
)
SELECT
    DATE(src.`start_date`) AS `stat_date`,
    src.`loan_id` AS `loan_id`,
    src.`action` AS `action`,
    COUNT(*) AS `record_count`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_collection_action AS src
WHERE src.`start_date` IS NOT NULL
  AND (DATE(src.`start_date`) IS NULL OR (DATE(src.`start_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`start_date`) <= CAST(@etl_end_date AS DATE)))
GROUP BY
    DATE(src.`start_date`),
    src.`loan_id`,
    src.`action`;
