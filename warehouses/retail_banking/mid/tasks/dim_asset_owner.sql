-- Human-reviewed semantic target: retail_banking_dm.dim_asset_owner
TRUNCATE TABLE retail_banking_dm.dim_asset_owner;

INSERT INTO retail_banking_dm.dim_asset_owner (
    `id`,
    `external_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`external_id`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_external_asset_owner AS src;
