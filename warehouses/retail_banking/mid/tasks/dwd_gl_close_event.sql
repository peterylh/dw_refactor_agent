SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_close_event
DELETE FROM retail_banking_dm.dwd_gl_close_event
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_gl_close_event
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_gl_close_event (
    `id`,
    `office_id`,
    `closing_date`,
    `is_deleted`,
    `createdby_id`,
    `lastmodifiedby_id`,
    `created_date`,
    `lastmodified_date`,
    `comments`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`office_id`,
    src.`closing_date`,
    src.`is_deleted`,
    src.`createdby_id`,
    src.`lastmodifiedby_id`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`comments`,
    DATE(src.`closing_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_gl_closure AS src
WHERE DATE(src.`closing_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`closing_date`) IS NULL;
