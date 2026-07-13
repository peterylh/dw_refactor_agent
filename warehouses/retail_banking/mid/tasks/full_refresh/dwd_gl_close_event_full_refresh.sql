SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_close_event
TRUNCATE TABLE retail_banking_dm.dwd_gl_close_event;

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
WHERE (DATE(src.`closing_date`) IS NULL OR (DATE(src.`closing_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`closing_date`) <= CAST(@etl_end_date AS DATE)));
