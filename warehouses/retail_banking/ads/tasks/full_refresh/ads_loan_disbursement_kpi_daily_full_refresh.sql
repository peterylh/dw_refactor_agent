SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.dws_loan_disbursement_daily
TRUNCATE TABLE retail_banking_dm.ads_loan_disbursement_kpi_daily;

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
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)));
