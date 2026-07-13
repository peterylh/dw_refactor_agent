SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed aggregation from dwd_loan_transaction
TRUNCATE TABLE retail_banking_dm.dws_loan_transaction_daily;

INSERT INTO retail_banking_dm.dws_loan_transaction_daily (
    `stat_date`,
    `office_id`,
    `loan_id`,
    `transaction_type_enum`,
    `record_count`,
    `total_amount`,
    `total_principal_component`,
    `total_interest_component`,
    `total_fee_component`,
    `total_penalty_component`,
    `etl_time`
)
SELECT
    DATE(src.`transaction_date`) AS `stat_date`,
    src.`office_id` AS `office_id`,
    src.`loan_id` AS `loan_id`,
    src.`transaction_type_enum` AS `transaction_type_enum`,
    COUNT(*) AS `record_count`,
    COALESCE(SUM(src.`amount`), 0) AS `total_amount`,
    COALESCE(SUM(src.`principal_portion_derived`), 0) AS `total_principal_component`,
    COALESCE(SUM(src.`interest_portion_derived`), 0) AS `total_interest_component`,
    COALESCE(SUM(src.`fee_charges_portion_derived`), 0) AS `total_fee_component`,
    COALESCE(SUM(src.`penalty_charges_portion_derived`), 0) AS `total_penalty_component`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.dwd_loan_transaction AS src
WHERE src.`transaction_date` IS NOT NULL
  AND (DATE(src.`transaction_date`) IS NULL OR (DATE(src.`transaction_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`transaction_date`) <= CAST(@etl_end_date AS DATE)))
  AND src.`is_reversed` = FALSE
GROUP BY
    DATE(src.`transaction_date`),
    src.`office_id`,
    src.`loan_id`,
    src.`transaction_type_enum`;
