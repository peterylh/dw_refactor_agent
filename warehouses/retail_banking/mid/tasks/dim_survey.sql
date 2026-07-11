SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_survey
TRUNCATE TABLE retail_banking_dm.dim_survey;

INSERT INTO retail_banking_dm.dim_survey (
    `id`,
    `a_key`,
    `a_name`,
    `description`,
    `country_code`,
    `valid_from`,
    `valid_to`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`a_key`,
    src.`a_name`,
    src.`description`,
    src.`country_code`,
    src.`valid_from`,
    src.`valid_to`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_surveys AS src;
