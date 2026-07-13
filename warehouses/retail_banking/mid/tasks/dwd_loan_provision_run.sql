SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_provision_run
DELETE FROM retail_banking_dm.dwd_loan_provision_run
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_provision_run
WHERE `business_date` IS NULL;

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
FROM retail_banking_dm.ods_fineract_m_provisioning_history AS src
WHERE DATE(src.`created_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`created_date`) IS NULL;
