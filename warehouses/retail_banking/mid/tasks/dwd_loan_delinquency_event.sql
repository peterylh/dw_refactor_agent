SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_delinquency_event
DELETE FROM retail_banking_dm.dwd_loan_delinquency_event
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_delinquency_event
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_loan_delinquency_event (
    `id`,
    `delinquency_range_id`,
    `loan_id`,
    `addedon_date`,
    `liftedon_date`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`delinquency_range_id`,
    src.`loan_id`,
    src.`addedon_date`,
    src.`liftedon_date`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`version`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    DATE(src.`addedon_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_delinquency_tag_history AS src
WHERE DATE(src.`addedon_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`addedon_date`) IS NULL;
