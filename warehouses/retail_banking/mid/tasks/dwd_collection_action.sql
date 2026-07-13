-- Human-reviewed semantic target: retail_banking_dm.dwd_collection_action
TRUNCATE TABLE retail_banking_dm.dwd_collection_action;

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
FROM retail_banking_dm.ods_fineract_m_loan_delinquency_action AS src;
