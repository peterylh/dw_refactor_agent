-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_guarantor_relation
TRUNCATE TABLE retail_banking_dm.dwd_loan_guarantor_relation;

INSERT INTO retail_banking_dm.dwd_loan_guarantor_relation (
    `id`,
    `loan_id`,
    `client_reln_cv_id`,
    `type_enum`,
    `entity_id`,
    `firstname`,
    `lastname`,
    `dob`,
    `address_line_1`,
    `address_line_2`,
    `city`,
    `state`,
    `country`,
    `zip`,
    `house_phone_number`,
    `mobile_number`,
    `comment`,
    `is_active`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`client_reln_cv_id`,
    src.`type_enum`,
    src.`entity_id`,
    CASE WHEN src.`firstname` IS NULL THEN NULL ELSE '***' END AS `firstname`,
    CASE WHEN src.`lastname` IS NULL THEN NULL ELSE '***' END AS `lastname`,
    CASE WHEN src.`dob` IS NULL THEN NULL ELSE '***' END AS `dob`,
    CASE WHEN src.`address_line_1` IS NULL THEN NULL ELSE '***' END AS `address_line_1`,
    CASE WHEN src.`address_line_2` IS NULL THEN NULL ELSE '***' END AS `address_line_2`,
    CASE WHEN src.`city` IS NULL THEN NULL ELSE '***' END AS `city`,
    src.`state`,
    src.`country`,
    CASE WHEN src.`zip` IS NULL THEN NULL ELSE '***' END AS `zip`,
    CASE WHEN src.`house_phone_number` IS NULL THEN NULL ELSE SHA2(CAST(src.`house_phone_number` AS STRING), 256) END AS `house_phone_number`,
    CASE WHEN src.`mobile_number` IS NULL THEN NULL ELSE SHA2(CAST(src.`mobile_number` AS STRING), 256) END AS `mobile_number`,
    CASE WHEN src.`comment` IS NULL THEN NULL ELSE '***' END AS `comment`,
    src.`is_active`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_guarantor AS src;
