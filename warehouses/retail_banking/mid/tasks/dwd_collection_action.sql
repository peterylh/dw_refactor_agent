SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_collection_action
DELETE FROM retail_banking_dm.dwd_collection_action
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_collection_action
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_collection_action (
    `id`,
    `loan_id`,
    `action`,
    `start_date`,
    `end_date`,
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
    src.`action`,
    src.`start_date`,
    src.`end_date`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    DATE(src.`start_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_delinquency_action AS src
WHERE DATE(src.`start_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`start_date`) IS NULL;
