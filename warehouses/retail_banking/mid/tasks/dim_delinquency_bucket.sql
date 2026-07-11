SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_delinquency_bucket
TRUNCATE TABLE retail_banking_dm.dim_delinquency_bucket;

INSERT INTO retail_banking_dm.dim_delinquency_bucket (
    `id`,
    `name`,
    `created_by`,
    `created_on_utc`,
    `version`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `bucket_type`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`version`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`bucket_type`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_delinquency_bucket AS src;
