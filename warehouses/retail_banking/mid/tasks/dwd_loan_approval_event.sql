SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_approval_event
DELETE FROM retail_banking_dm.dwd_loan_approval_event
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_approval_event
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_loan_approval_event (
    `id`,
    `loan_id`,
    `new_approved_amount`,
    `old_approved_amount`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`new_approved_amount`,
    src.`old_approved_amount`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    DATE(src.`created_on_utc`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_approved_amount_history AS src
WHERE DATE(src.`created_on_utc`) = CAST(@etl_date AS DATE)
   OR DATE(src.`created_on_utc`) IS NULL;
