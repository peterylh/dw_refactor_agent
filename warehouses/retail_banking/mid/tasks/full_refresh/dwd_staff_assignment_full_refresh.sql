SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_staff_assignment
TRUNCATE TABLE retail_banking_dm.dwd_staff_assignment;

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
WHERE (DATE(src.`start_date`) IS NULL OR (DATE(src.`start_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`start_date`) <= CAST(@etl_end_date AS DATE)));
