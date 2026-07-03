-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_atm_locations;

INSERT INTO finance_analytics_dm.dwd_atm_locations
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_atm_locations
),

cleaned AS (
    SELECT
        -- Primary Key
        atm_id,
        atm_code,
        
        -- Location Information
        TRIM(location_name) AS location_name,
        location_type,
        
        -- Address Details
        TRIM(address) AS address,
        TRIM(city) AS city,
        UPPER(TRIM(state)) AS state,
        zip_code,
        UPPER(TRIM(country)) AS country,
        latitude,
        longitude,
        
        -- Operational Status
        install_date,
        is_operational,
        is_24_hour,
        
        -- Capabilities
        is_deposit_enabled,
        is_cash_only,
        CAST(max_withdrawal_amount AS DECIMAL(10,2)) AS max_withdrawal_amount,
        daily_transaction_limit,
        
        -- Operational Metrics
        avg_daily_transactions,
        CAST(cash_capacity AS DECIMAL(12,2)) AS cash_capacity,
        
        -- Maintenance
        last_refill_date,
        last_maintenance_date,
        
        -- Fees & Security
        CAST(surcharge_fee AS DECIMAL(5,2)) AS surcharge_fee,
        has_camera,
        
        -- Relationships
        branch_id,
        
        -- Metadata
        CURRENT_TIMESTAMP AS created_at
        
    FROM source
    WHERE atm_id IS NOT NULL
)

SELECT * FROM cleaned;
