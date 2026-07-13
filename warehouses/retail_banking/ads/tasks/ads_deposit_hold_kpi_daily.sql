-- Reviewed application metrics derived from retail_banking_dm.dws_deposit_hold_event_daily
TRUNCATE TABLE retail_banking_dm.ads_deposit_hold_kpi_daily;

INSERT INTO retail_banking_dm.ads_deposit_hold_kpi_daily (
    `stat_date`,
    `savings_account_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `average_hold_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`savings_account_id`,
    src.`transaction_type_enum`,
    src.`record_count` AS `record_count`,
    src.`total_amount` AS `total_amount`,
    (src.`total_amount`) / nullif((src.`record_count`), 0) AS `average_hold_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_deposit_hold_event_daily AS src;
