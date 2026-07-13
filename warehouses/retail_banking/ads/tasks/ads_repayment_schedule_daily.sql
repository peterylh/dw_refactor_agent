SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Reviewed application metrics derived from retail_banking_dm.dws_loan_installment_due_daily
DELETE FROM retail_banking_dm.ads_repayment_schedule_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

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
WHERE src.`stat_date` = CAST(@etl_date AS DATE);
