SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_deposit_officer_assignment
TRUNCATE TABLE retail_banking_dm.dwd_deposit_officer_assignment;

INSERT INTO retail_banking_dm.dwd_deposit_officer_assignment (
    `id`,
    `account_id`,
    `savings_officer_id`,
    `start_date`,
    `end_date`,
    `created_by`,
    `created_date`,
    `lastmodified_date`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`account_id`,
    src.`savings_officer_id`,
    src.`start_date`,
    src.`end_date`,
    src.`created_by`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    DATE(src.`start_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_savings_officer_assignment_history AS src;
