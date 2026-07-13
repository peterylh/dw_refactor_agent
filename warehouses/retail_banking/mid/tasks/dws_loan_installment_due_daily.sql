SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed aggregation from dwd_loan_installment
DELETE FROM retail_banking_dm.dws_loan_installment_due_daily
WHERE `stat_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dws_loan_installment_due_daily (
    `stat_date`,
    `loan_id`,
    `installment_count`,
    `scheduled_principal_amount`,
    `scheduled_interest_amount`,
    `scheduled_fee_amount`,
    `scheduled_penalty_amount`,
    `etl_time`
)
SELECT
    DATE(src.`duedate`) AS `stat_date`,
    src.`loan_id` AS `loan_id`,
    COUNT(*) AS `installment_count`,
    COALESCE(SUM(src.`principal_amount`), 0) AS `scheduled_principal_amount`,
    COALESCE(SUM(src.`interest_amount`), 0) AS `scheduled_interest_amount`,
    COALESCE(SUM(src.`fee_charges_amount`), 0) AS `scheduled_fee_amount`,
    COALESCE(SUM(src.`penalty_charges_amount`), 0) AS `scheduled_penalty_amount`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_installment AS src
WHERE src.`duedate` IS NOT NULL
  AND DATE(src.`duedate`) = CAST(@etl_date AS DATE)
GROUP BY
    DATE(src.`duedate`),
    src.`loan_id`;
