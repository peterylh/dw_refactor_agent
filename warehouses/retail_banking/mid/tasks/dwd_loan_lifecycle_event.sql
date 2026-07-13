SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_lifecycle_event
DELETE FROM retail_banking_dm.dwd_loan_lifecycle_event
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_lifecycle_event
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_loan_lifecycle_event (
    `id`,
    `loan_id`,
    `status_code`,
    `status_change_business_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`status_code`,
    src.`status_change_business_date`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    DATE(src.`status_change_business_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_status_change_history AS src
WHERE DATE(src.`status_change_business_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`status_change_business_date`) IS NULL;
