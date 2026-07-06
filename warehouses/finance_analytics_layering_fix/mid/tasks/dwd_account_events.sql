-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_account_events;

INSERT INTO finance_analytics_dm.dwd_account_events
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_account_events
),

cleaned AS (
    SELECT
        -- Primary Keys
        event_id,
        account_id,
        customer_id,
        product_id,
        
        -- Event Details
        event_date,
        TRIM(event_type) AS event_type,
        event_category,
        
        -- Change Values
        old_value,
        new_value,
        
        -- Event Metadata
        triggered_by,
        channel,
        TRIM(processed_by) AS processed_by,
        TRIM(notes) AS notes,
        
        -- Flags
        is_reversible,
        requires_approval,
        approval_status,
        
        -- Metadata
        CURRENT_TIMESTAMP AS created_at
        
    FROM source
    WHERE event_id IS NOT NULL
      AND account_id IS NOT NULL
      AND customer_id IS NOT NULL
)

SELECT * FROM cleaned;
