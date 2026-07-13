-- Human-reviewed semantic target: retail_banking_dm.dim_rate_index
TRUNCATE TABLE retail_banking_dm.dim_rate_index;

INSERT INTO retail_banking_dm.dim_rate_index (
    `id`,
    `name`,
    `is_base_lending_rate`,
    `is_active`,
    `created_by`,
    `created_date`,
    `last_modified_by`,
    `lastmodified_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`is_base_lending_rate`,
    src.`is_active`,
    src.`created_by`,
    src.`created_date`,
    src.`last_modified_by`,
    src.`lastmodified_date`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_floating_rates AS src;
