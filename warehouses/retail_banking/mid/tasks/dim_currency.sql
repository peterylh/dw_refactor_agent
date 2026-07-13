-- Human-reviewed semantic target: retail_banking_dm.dim_currency
TRUNCATE TABLE retail_banking_dm.dim_currency;

INSERT INTO retail_banking_dm.dim_currency (
    `id`,
    `code`,
    `decimal_places`,
    `currency_multiplesof`,
    `display_symbol`,
    `name`,
    `internationalized_name_code`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`code`,
    src.`decimal_places`,
    src.`currency_multiplesof`,
    src.`display_symbol`,
    src.`name`,
    src.`internationalized_name_code`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_currency AS src;
