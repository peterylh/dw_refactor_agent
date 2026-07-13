SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_staff_assignment
DELETE FROM retail_banking_dm.dwd_staff_assignment
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_staff_assignment
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_staff_assignment (
    `id`,
    `centre_id`,
    `staff_id`,
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
    src.`centre_id`,
    src.`staff_id`,
    src.`start_date`,
    src.`end_date`,
    src.`createdby_id`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`lastmodifiedby_id`,
    DATE(src.`start_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_staff_assignment_history AS src
WHERE DATE(src.`start_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`start_date`) IS NULL;
