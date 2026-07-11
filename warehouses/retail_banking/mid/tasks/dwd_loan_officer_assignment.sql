SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_officer_assignment
TRUNCATE TABLE retail_banking_dm.dwd_loan_officer_assignment;

INSERT INTO retail_banking_dm.dwd_loan_officer_assignment (
    `id`,
    `loan_id`,
    `loan_officer_id`,
    `start_date`,
    `end_date`,
    `createdby_id`,
    `created_date`,
    `lastmodified_date`,
    `lastmodifiedby_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`loan_officer_id`,
    src.`start_date`,
    src.`end_date`,
    src.`createdby_id`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`lastmodifiedby_id`,
    DATE(src.`start_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_officer_assignment_history AS src;
