-- Human-reviewed semantic target: retail_banking_dm.dim_provision_category
TRUNCATE TABLE retail_banking_dm.dim_provision_category;

INSERT INTO retail_banking_dm.dim_provision_category (
    `id`,
    `category_name`,
    `description`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`category_name`,
    src.`description`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_provision_category AS src;
