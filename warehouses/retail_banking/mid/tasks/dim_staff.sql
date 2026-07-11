SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_staff
TRUNCATE TABLE retail_banking_dm.dim_staff;

INSERT INTO retail_banking_dm.dim_staff (
    `id`,
    `is_loan_officer`,
    `office_id`,
    `firstname`,
    `lastname`,
    `display_name`,
    `mobile_no`,
    `external_id`,
    `organisational_role_enum`,
    `organisational_role_parent_staff_id`,
    `is_active`,
    `joining_date`,
    `image_id`,
    `email_address`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`is_loan_officer`,
    src.`office_id`,
    CASE WHEN src.`firstname` IS NULL THEN NULL ELSE '***' END AS `firstname`,
    CASE WHEN src.`lastname` IS NULL THEN NULL ELSE '***' END AS `lastname`,
    CASE WHEN src.`display_name` IS NULL THEN NULL ELSE '***' END AS `display_name`,
    CASE WHEN src.`mobile_no` IS NULL THEN NULL ELSE SHA2(CAST(src.`mobile_no` AS STRING), 256) END AS `mobile_no`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`organisational_role_enum`,
    src.`organisational_role_parent_staff_id`,
    src.`is_active`,
    src.`joining_date`,
    src.`image_id`,
    CASE WHEN src.`email_address` IS NULL THEN NULL ELSE SHA2(CAST(src.`email_address` AS STRING), 256) END AS `email_address`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_staff AS src;
