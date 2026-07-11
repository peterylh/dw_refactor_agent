SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_credit_bureau
TRUNCATE TABLE retail_banking_dm.dim_credit_bureau;

INSERT INTO retail_banking_dm.dim_credit_bureau (
    `id`,
    `name`,
    `product`,
    `country`,
    `implementation_key`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`product`,
    src.`country`,
    src.`implementation_key`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_creditbureau AS src;
