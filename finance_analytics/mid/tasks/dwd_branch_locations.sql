-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_branch_locations;

INSERT INTO finance_analytics_dm.dwd_branch_locations
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_branch_locations
),

cleaned AS (
    SELECT
        -- Primary Key
        branch_id,
        branch_code,
        
        -- Branch Information
        TRIM(branch_name) AS branch_name,
        branch_type,
        region,
        
        -- Location Details
        TRIM(address) AS address,
        TRIM(city) AS city,
        UPPER(TRIM(state)) AS state,
        zip_code,
        UPPER(TRIM(country)) AS country,
        latitude,
        longitude,
        
        -- Contact
        TRIM(phone) AS phone,
        
        -- Operational Details
        open_date,
        is_active,
        operating_hours,
        
        -- Capacity Metrics
        square_footage,
        num_employees,
        avg_daily_customers,
        
        -- Services Available
        has_safe_deposit,
        has_notary,
        has_coin_counter,
        wheelchair_accessible,
        
        -- Management
        TRIM(manager_name) AS manager_name,
        
        -- Metadata
        CURRENT_TIMESTAMP AS  created_at
        
    FROM source
    WHERE branch_id IS NOT NULL
)

SELECT * FROM cleaned;
