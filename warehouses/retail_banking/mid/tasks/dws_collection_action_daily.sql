SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_collection_action
DELETE FROM retail_banking_dm.dws_collection_action_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

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
  AND DATE(src.`start_date`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`start_date`),
    src.`loan_id`,
    src.`action`;
