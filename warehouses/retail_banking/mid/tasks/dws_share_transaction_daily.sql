-- Human-reviewed aggregation from dwd_share_transaction
TRUNCATE TABLE retail_banking_dm.dws_share_transaction_daily;

INSERT INTO retail_banking_dm.dws_share_transaction_daily (
    `stat_date`,
    `account_id`,
    `type_enum`,
    `status_enum`,
    `record_count`,
    `total_shares`,
    `total_amount`,
    `total_charge_amount`,
    `total_amount_paid`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`account_id` AS `account_id`,
    src.`type_enum` AS `type_enum`,
    src.`status_enum` AS `status_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`total_shares`), 0) AS `total_shares`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    COALESCE(SUM(src.`charge_amount`), 0) AS `total_charge_amount`,
    COALESCE(SUM(src.`amount_paid`), 0) AS `total_amount_paid`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_share_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND src.`is_active` = TRUE
GROUP BY
    DATE(src.`transaction_date`),
    src.`account_id`,
    src.`type_enum`,
    src.`status_enum`;
