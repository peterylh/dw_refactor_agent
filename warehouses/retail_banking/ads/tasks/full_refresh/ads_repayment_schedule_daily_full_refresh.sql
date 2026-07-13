SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Reviewed application metrics derived from retail_banking_dm.dws_loan_installment_due_daily
TRUNCATE TABLE retail_banking_dm.ads_repayment_schedule_daily;

INSERT INTO retail_banking_dm.ads_repayment_schedule_daily (
    `stat_date`,
    `loan_id`,
    `installment_count`,
    `scheduled_total_amount`,
    `average_scheduled_amount`,
    `etl_time`
)
SELECT
    src.`stat_date`,
    src.`loan_id`,
    src.`installment_count` AS `installment_count`,
    src.`scheduled_principal_amount` + src.`scheduled_interest_amount` + src.`scheduled_fee_amount` + src.`scheduled_penalty_amount` AS `scheduled_total_amount`,
    (src.`scheduled_principal_amount` + src.`scheduled_interest_amount` + src.`scheduled_fee_amount` + src.`scheduled_penalty_amount`) / nullif((src.`installment_count`), 0) AS `average_scheduled_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dws_loan_installment_due_daily AS src
WHERE (src.`stat_date` IS NULL OR (src.`stat_date` >= CAST(@etl_start_date AS DATE) AND src.`stat_date` <= CAST(@etl_end_date AS DATE)));
