SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_code_value
TRUNCATE TABLE retail_banking_dm.dim_code_value;

INSERT INTO retail_banking_dm.dim_code_value (
    `id`,
    `code_id`,
    `code_value`,
    `code_description`,
    `order_position`,
    `code_score`,
    `is_active`,
    `is_mandatory`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`code_id`,
    src.`code_value`,
    src.`code_description`,
    src.`order_position`,
    src.`code_score`,
    src.`is_active`,
    src.`is_mandatory`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_code_value AS src;
