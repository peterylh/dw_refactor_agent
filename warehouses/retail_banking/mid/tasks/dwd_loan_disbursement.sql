SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_disbursement
DELETE FROM retail_banking_dm.dwd_loan_disbursement
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_disbursement
WHERE `business_date` IS NULL;

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
WHERE DATE(src.`disbursedon_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`disbursedon_date`) IS NULL;
