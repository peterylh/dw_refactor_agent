SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_loan_ownership_transfer
TRUNCATE TABLE retail_banking_dm.dws_loan_ownership_settlement_daily;

INSERT INTO retail_banking_dm.dws_loan_ownership_settlement_daily (
    `stat_date`,
    `owner_id`,
    `loan_id`,
    `status`,
    `settlement_count`,
    `etl_time`
)
SELECT
    DATE(src.`settlement_date`) AS `stat_date`,
    src.`owner_id` AS `owner_id`,
    src.`loan_id` AS `loan_id`,
    src.`status` AS `status`,
    COUNT(*) AS `settlement_count`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_ownership_transfer AS src
WHERE src.`settlement_date` IS NOT NULL
  AND (DATE(src.`settlement_date`) IS NULL OR (DATE(src.`settlement_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`settlement_date`) <= CAST(@etl_end_date AS DATE)))
  AND src.`status` IN ('ACTIVE', 'BUYBACK')
GROUP BY
    DATE(src.`settlement_date`),
    src.`owner_id`,
    src.`loan_id`,
    src.`status`;
