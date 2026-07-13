SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_wc_breach_event
DELETE FROM retail_banking_dm.dws_wc_breach_start_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_wc_breach_start_daily (
    `stat_date`,
    `wc_loan_id`,
    `action`,
    `breach_start_count`,
    `etl_time`
)
SELECT
    DATE(src.`start_date`) AS `stat_date`,
    src.`wc_loan_id` AS `wc_loan_id`,
    src.`action` AS `action`,
    COUNT(*) AS `breach_start_count`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_wc_breach_event AS src
WHERE src.`start_date` IS NOT NULL
  AND DATE(src.`start_date`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`start_date`),
    src.`wc_loan_id`,
    src.`action`;
