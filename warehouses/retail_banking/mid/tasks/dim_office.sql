SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_office
TRUNCATE TABLE retail_banking_dm.dim_office;

INSERT INTO retail_banking_dm.dim_office (
    `id`,
    `parent_id`,
    `hierarchy`,
    `external_id`,
    `name`,
    `opening_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`parent_id`,
    src.`hierarchy`,
    src.`external_id`,
    src.`name`,
    src.`opening_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_office AS src;
