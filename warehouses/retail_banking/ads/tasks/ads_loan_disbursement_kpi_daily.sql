SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Reviewed application metrics derived from retail_banking_dm.dws_loan_disbursement_daily
DELETE FROM retail_banking_dm.ads_loan_disbursement_kpi_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.ads_loan_disbursement_kpi_daily (
    `stat_date`,
    `loan_id`,
    `record_count`,
    `total_principal`,
    `total_net_disbursal_amount`,
    `average_principal`,
    `net_disbursal_ratio`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`loan_id`,
    src.`record_count` AS `record_count`,
    src.`total_principal` AS `total_principal`,
    src.`total_net_disbursal_amount` AS `total_net_disbursal_amount`,
    (src.`total_principal`) / nullif((src.`record_count`), 0) AS `average_principal`,
    (src.`total_net_disbursal_amount`) / nullif((src.`total_principal`), 0) AS `net_disbursal_ratio`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_loan_disbursement_daily AS src
WHERE src.`stat_date` = CAST(@etl_date AS DATE);
