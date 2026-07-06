-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_account_events;

INSERT INTO finance_analytics_dm.dws_account_events
WITH account_event_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(ae.event_id AS STRING), '_dbt_null_'))) AS event_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ae.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ae.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ae.product_id AS STRING), '_dbt_null_'))) AS product_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(ae.event_date AS DATE) AS STRING), '_dbt_null_'))) AS event_date_key,
        
        ae.event_id,
        ae.event_date,
        ae.event_type,
        ae.event_category,
        ae.triggered_by,
        ae.channel,
        ae.processed_by,
        ae.approval_status,
        
        -- Event Values
        ae.old_value,
        ae.new_value,
        
        -- Attempt to parse numeric changes
        CASE
            WHEN ae.old_value IS NOT NULL AND ae.new_value IS NOT NULL
            THEN CAST(ae.new_value AS DECIMAL(18,4)) - CAST(ae.old_value AS DECIMAL(18,4))
            ELSE NULL
        END AS value_change,
        
        -- Flags
        CASE WHEN ae.is_reversible THEN 1 ELSE 0 END AS reversible_flag,
        CASE WHEN ae.requires_approval THEN 1 ELSE 0 END AS requires_approval_flag,
        CASE WHEN ae.approval_status = 'Approved' THEN 1 ELSE 0 END AS approved_flag,
        CASE WHEN ae.approval_status = 'Pending' THEN 1 ELSE 0 END AS pending_flag,
        CASE WHEN ae.approval_status = 'Rejected' THEN 1 ELSE 0 END AS rejected_flag,
        
        -- Event Type Categories
        CASE
            WHEN ae.event_type IN ('Account Opened', 'Account Closed', 'Account Reactivated') 
                THEN 'Lifecycle'
            WHEN ae.event_type IN ('Balance Update', 'Credit Limit Change', 'Interest Rate Change')
                THEN 'Financial'
            WHEN ae.event_type IN ('Status Change', 'Ownership Transfer')
                THEN 'Administrative'
            ELSE 'Other'
        END AS event_type_category,
        
        -- Counts
        1 AS event_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_account_events ae
)

SELECT * FROM account_event_facts;
