SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_customer_group_level
TRUNCATE TABLE retail_banking_dm.dim_customer_group_level;

INSERT INTO retail_banking_dm.dim_customer_group_level (
    `id`,
    `parent_id`,
    `super_parent`,
    `level_name`,
    `recursable`,
    `can_have_clients`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`parent_id`,
    src.`super_parent`,
    src.`level_name`,
    src.`recursable`,
    src.`can_have_clients`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_group_level AS src;
