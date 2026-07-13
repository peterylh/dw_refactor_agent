SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_loan_provision_entry
DELETE FROM retail_banking_dm.dws_loan_provision_run_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_loan_provision_run_daily (
    `stat_date`,
    `office_id`,
    `product_id`,
    `category_id`,
    `currency_code`,
    `journal_entry_created`,
    `provision_entry_count`,
    `total_reserve_amount`,
    `etl_time`
)
SELECT
    DATE(src.`provision_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`product_id` AS `product_id`,
    src.`category_id` AS `category_id`,
    src.`currency_code` AS `currency_code`,
    src.`journal_entry_created` AS `journal_entry_created`,
    COUNT(*) AS `provision_entry_count`,
    COALESCE(SUM(src.`reseve_amount`), 0) AS `total_reserve_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_provision_entry AS src
WHERE src.`provision_date` IS NOT NULL
  AND DATE(src.`provision_date`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`provision_date`),
    src.`office_id`,
    src.`product_id`,
    src.`category_id`,
    src.`currency_code`,
    src.`journal_entry_created`;
