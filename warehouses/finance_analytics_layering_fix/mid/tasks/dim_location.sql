-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_location;

INSERT INTO finance_analytics_dm.dim_location
WITH branches AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(branch_id AS STRING), '_dbt_null_'))) AS location_key,
        branch_id AS location_natural_key,
        'BRANCH' AS location_type,
        branch_name AS location_name,
        branch_code AS location_code,
        address,
        city,
        state,
        zip_code,
        country,
        latitude,
        longitude,
        region,
        phone,
        CAST(is_active AS BOOLEAN) AS is_active,
        CAST(NULL AS BOOLEAN) AS is_operational,
        CAST(NULL AS BOOLEAN) AS is_24_hour
    FROM finance_analytics_dm.dwd_branch_locations
),

atms AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(atm_id AS STRING), '_dbt_null_'))) AS location_key,
        atm_id AS location_natural_key,
        'ATM' AS location_type,
        location_name,
        atm_code AS location_code,
        address,
        city,
        state,
        zip_code,
        country,
        latitude,
        longitude,
        CAST(NULL AS TEXT) AS region,
        CAST(NULL AS TEXT) AS phone,
        CAST(NULL AS BOOLEAN) AS is_active,
        CAST(is_operational AS BOOLEAN) AS is_operational,
        CAST(is_24_hour AS BOOLEAN) AS is_24_hour
    FROM finance_analytics_dm.dwd_atm_locations
),

combined_locations AS (
    SELECT * FROM branches
    UNION ALL
    SELECT * FROM atms
)

SELECT 
    *,
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM combined_locations;
