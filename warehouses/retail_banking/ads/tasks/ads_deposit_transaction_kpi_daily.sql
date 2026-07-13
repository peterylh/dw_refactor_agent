-- Reviewed application metrics derived from retail_banking_dm.dws_deposit_transaction_daily
TRUNCATE TABLE retail_banking_dm.ads_deposit_transaction_kpi_daily;

INSERT INTO retail_banking_dm.ads_deposit_transaction_kpi_daily (
    `stat_date`,
    `office_id`,
    `savings_account_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `total_overdraft_amount`,
    `average_amount`,
    `overdraft_amount_ratio`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`office_id`,
    src.`savings_account_id`,
    src.`transaction_type_enum`,
    src.`record_count` AS `record_count`,
    src.`total_amount` AS `total_amount`,
    src.`total_overdraft_amount` AS `total_overdraft_amount`,
    (src.`total_amount`) / nullif((src.`record_count`), 0) AS `average_amount`,
    (src.`total_overdraft_amount`) / nullif((src.`total_amount`), 0) AS `overdraft_amount_ratio`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_deposit_transaction_daily AS src;
