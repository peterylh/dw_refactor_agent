SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_payment_type
TRUNCATE TABLE retail_banking_dm.dim_payment_type;

INSERT INTO retail_banking_dm.dim_payment_type (
    `id`,
    `value`,
    `description`,
    `is_cash_payment`,
    `order_position`,
    `code_name`,
    `is_system_defined`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`value`,
    src.`description`,
    src.`is_cash_payment`,
    src.`order_position`,
    src.`code_name`,
    src.`is_system_defined`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_payment_type AS src;
