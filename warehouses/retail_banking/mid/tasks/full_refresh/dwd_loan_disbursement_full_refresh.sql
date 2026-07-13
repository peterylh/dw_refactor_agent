SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_disbursement
TRUNCATE TABLE retail_banking_dm.dwd_loan_disbursement;

INSERT INTO retail_banking_dm.dwd_loan_disbursement (
    `id`,
    `loan_id`,
    `expected_disburse_date`,
    `disbursedon_date`,
    `principal`,
    `net_disbursal_amount`,
    `is_reversed`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`expected_disburse_date`,
    src.`disbursedon_date`,
    src.`principal`,
    src.`net_disbursal_amount`,
    src.`is_reversed`,
    DATE(src.`disbursedon_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_disbursement_detail AS src
WHERE (DATE(src.`disbursedon_date`) IS NULL OR (DATE(src.`disbursedon_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`disbursedon_date`) <= CAST(@etl_end_date AS DATE)));
