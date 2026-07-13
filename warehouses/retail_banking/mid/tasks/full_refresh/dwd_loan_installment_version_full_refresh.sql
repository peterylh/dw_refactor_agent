SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_installment_version
TRUNCATE TABLE retail_banking_dm.dwd_loan_installment_version;

INSERT INTO retail_banking_dm.dwd_loan_installment_version (
    `id`,
    `loan_id`,
    `loan_reschedule_request_id`,
    `fromdate`,
    `duedate`,
    `installment`,
    `principal_amount`,
    `interest_amount`,
    `fee_charges_amount`,
    `penalty_charges_amount`,
    `createdby_id`,
    `created_date`,
    `lastmodified_date`,
    `lastmodifiedby_id`,
    `version`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`loan_reschedule_request_id`,
    src.`fromdate`,
    src.`duedate`,
    src.`installment`,
    src.`principal_amount`,
    src.`interest_amount`,
    src.`fee_charges_amount`,
    src.`penalty_charges_amount`,
    src.`createdby_id`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`lastmodifiedby_id`,
    src.`version`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    DATE(src.`duedate`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_repayment_schedule_history AS src
WHERE (DATE(src.`duedate`) IS NULL OR (DATE(src.`duedate`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`duedate`) <= CAST(@etl_end_date AS DATE)));
