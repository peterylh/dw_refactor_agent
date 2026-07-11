SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_loan_rate
TRUNCATE TABLE retail_banking_dm.bridge_loan_rate;

INSERT INTO retail_banking_dm.bridge_loan_rate (
    `loan_id`,
    `rate_id`,
    `etl_time`
)
SELECT
    src.`loan_id`,
    src.`rate_id`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_rate AS src;
