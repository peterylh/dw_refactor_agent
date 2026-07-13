-- Human-reviewed semantic target: retail_banking_dm.dim_delinquency_range
TRUNCATE TABLE retail_banking_dm.dim_delinquency_range;

INSERT INTO retail_banking_dm.dim_delinquency_range (
    `id`,
    `classification`,
    `min_age_days`,
    `max_age_days`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`classification`,
    src.`min_age_days`,
    src.`max_age_days`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`version`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_delinquency_range AS src;
