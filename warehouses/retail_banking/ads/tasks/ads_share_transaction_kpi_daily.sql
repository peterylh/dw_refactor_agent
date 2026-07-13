SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Reviewed application metrics derived from retail_banking_dm.dws_share_transaction_daily
DELETE FROM retail_banking_dm.ads_share_transaction_kpi_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.ads_share_transaction_kpi_daily (
    `stat_date`,
    `account_id`,
    `type_enum`,
    `status_enum`,
    `record_count`,
    `total_shares`,
    `total_amount`,
    `average_share_price`,
    `paid_ratio`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`account_id`,
    src.`type_enum`,
    src.`status_enum`,
    src.`record_count` AS `record_count`,
    src.`total_shares` AS `total_shares`,
    src.`total_amount` AS `total_amount`,
    (src.`total_amount`) / nullif((src.`total_shares`), 0) AS `average_share_price`,
    src.`total_amount_paid` / nullif((src.`total_amount`), 0) AS `paid_ratio`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_share_transaction_daily AS src
WHERE src.`stat_date` = CAST(@etl_date AS DATE);
