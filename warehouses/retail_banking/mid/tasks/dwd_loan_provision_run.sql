SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_provision_run
TRUNCATE TABLE retail_banking_dm.dwd_loan_provision_run;

INSERT INTO retail_banking_dm.dwd_loan_provision_run (
    `id`,
    `journal_entry_created`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`journal_entry_created`,
    src.`createdby_id`,
    src.`created_date`,
    src.`lastmodifiedby_id`,
    src.`lastmodified_date`,
    DATE(src.`created_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_provisioning_history AS src;
