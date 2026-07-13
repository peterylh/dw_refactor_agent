SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Reviewed application metrics derived from retail_banking_dm.dws_office_cash_transfer_daily
DELETE FROM retail_banking_dm.ads_branch_cash_transfer_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.ads_branch_cash_transfer_daily (
    `stat_date`,
    `from_office_id`,
    `to_office_id`,
    `currency_code`,
    `record_count`,
    `total_transaction_amount`,
    `average_transaction_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`from_office_id`,
    src.`to_office_id`,
    src.`currency_code`,
    src.`record_count` AS `record_count`,
    src.`total_transaction_amount` AS `total_transaction_amount`,
    (src.`total_transaction_amount`) / nullif((src.`record_count`), 0) AS `average_transaction_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_office_cash_transfer_daily AS src
WHERE src.`stat_date` = CAST(@etl_date AS DATE);
