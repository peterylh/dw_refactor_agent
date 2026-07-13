SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_wc_loan_disbursement
DELETE FROM retail_banking_dm.dwd_wc_loan_disbursement
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_wc_loan_disbursement
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_wc_loan_disbursement (
    `id`,
    `wc_loan_id`,
    `expected_disburse_date`,
    `expected_amount`,
    `expected_maturity_date`,
    `actual_disburse_date`,
    `actual_amount`,
    `disbursedon_userid`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`wc_loan_id`,
    src.`expected_disburse_date`,
    src.`expected_amount`,
    src.`expected_maturity_date`,
    src.`actual_disburse_date`,
    src.`actual_amount`,
    src.`disbursedon_userid`,
    DATE(src.`actual_disburse_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_wc_loan_disbursement_detail AS src
WHERE DATE(src.`actual_disburse_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`actual_disburse_date`) IS NULL;
