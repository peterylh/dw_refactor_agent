SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_customer_group
TRUNCATE TABLE retail_banking_dm.dim_customer_group;

INSERT INTO retail_banking_dm.dim_customer_group (
    `id`,
    `external_id`,
    `status_enum`,
    `activation_date`,
    `office_id`,
    `staff_id`,
    `parent_id`,
    `level_id`,
    `display_name`,
    `hierarchy`,
    `closure_reason_cv_id`,
    `closedon_date`,
    `activatedon_userid`,
    `submittedon_date`,
    `submittedon_userid`,
    `closedon_userid`,
    `account_no`,
    `etl_time`
)
SELECT
    src.`id`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`status_enum`,
    src.`activation_date`,
    src.`office_id`,
    src.`staff_id`,
    src.`parent_id`,
    src.`level_id`,
    CASE WHEN src.`display_name` IS NULL THEN NULL ELSE '***' END AS `display_name`,
    src.`hierarchy`,
    src.`closure_reason_cv_id`,
    src.`closedon_date`,
    src.`activatedon_userid`,
    src.`submittedon_date`,
    src.`submittedon_userid`,
    src.`closedon_userid`,
    CASE WHEN src.`account_no` IS NULL THEN NULL ELSE SHA2(CAST(src.`account_no` AS STRING), 256) END AS `account_no`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_group AS src;
