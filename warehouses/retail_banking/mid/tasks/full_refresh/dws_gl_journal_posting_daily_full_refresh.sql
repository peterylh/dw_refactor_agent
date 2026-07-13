SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_gl_journal_entry
TRUNCATE TABLE retail_banking_dm.dws_gl_journal_posting_daily;

INSERT INTO retail_banking_dm.dws_gl_journal_posting_daily (
    `stat_date`,
    `transaction_id`,
    `office_id`,
    `account_id`,
    `currency_code`,
    `type_enum`,
    `record_count`,
    `total_amount`,
    `etl_time`
)
SELECT
    DATE(src.`entry_date`) AS `stat_date`,
    src.`transaction_id` AS `transaction_id`,
    src.`office_id` AS `office_id`,
    src.`account_id` AS `account_id`,
    src.`currency_code` AS `currency_code`,
    src.`type_enum` AS `type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_gl_journal_entry AS src
WHERE src.`entry_date` IS NOT NULL
  AND (DATE(src.`entry_date`) IS NULL OR (DATE(src.`entry_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`entry_date`) <= CAST(@etl_end_date AS DATE)))
  AND src.`reversed` = FALSE
GROUP BY
    DATE(src.`entry_date`),
    src.`transaction_id`,
    src.`office_id`,
    src.`account_id`,
    src.`currency_code`,
    src.`type_enum`;
