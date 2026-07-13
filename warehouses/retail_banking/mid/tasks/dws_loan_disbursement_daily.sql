-- Human-reviewed aggregation from dwd_loan_disbursement
TRUNCATE TABLE retail_banking_dm.dws_loan_disbursement_daily;

INSERT INTO retail_banking_dm.dws_loan_disbursement_daily (
    `stat_date`,
    `loan_id`,
    `record_count`,
    `total_principal`,
    `total_net_disbursal_amount`,
    `etl_time`
)
SELECT
    DATE(src.`disbursedon_date`) AS `stat_date`,
    src.`loan_id` AS `loan_id`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`principal`), 0) AS `total_principal`,
    COALESCE(SUM(src.`net_disbursal_amount`), 0) AS `total_net_disbursal_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_disbursement AS src
WHERE src.`disbursedon_date` IS NOT NULL
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`disbursedon_date`),
    src.`loan_id`;
