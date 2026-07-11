-- Human-reviewed aggregation from dwd_deposit_transaction
TRUNCATE TABLE retail_banking_dm.dws_deposit_transaction_daily;

INSERT INTO retail_banking_dm.dws_deposit_transaction_daily (
    `stat_date`,
    `office_id`,
    `savings_account_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `total_overdraft_amount`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`savings_account_id` AS `savings_account_id`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    COALESCE(SUM(src.`overdraft_amount_derived`), 0) AS `total_overdraft_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_deposit_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`office_id`,
    src.`savings_account_id`,
    src.`transaction_type_enum`;
