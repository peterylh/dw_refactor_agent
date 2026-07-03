-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_fraud_alerts;

INSERT INTO finance_analytics_dm.dwd_fraud_alerts
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_fraud_alerts
),

cleaned AS (
    SELECT
        alert_id,
        transaction_id,
        customer_id,
        account_id,
        alert_date,
        alert_type,
        alert_severity,
        investigation_status,
        resolution_date,
        amount_recovered,
        assigned_to,
        notes,
        
        -- Time to Resolution
        CASE 
            WHEN resolution_date IS NOT NULL 
            THEN DAY((resolution_date - alert_date))
            ELSE NULL
        END AS resolution_days,
        
        -- Status Flags
        CASE 
            WHEN investigation_status IN ('Resolved - Fraud', 'Resolved - Legitimate', 'False Positive') 
            THEN TRUE 
            ELSE FALSE 
        END AS is_resolved,
        
        CASE 
            WHEN investigation_status = 'Resolved - Fraud' 
            THEN TRUE 
            ELSE FALSE 
        END AS is_confirmed_fraud,
        
        CASE 
            WHEN investigation_status = 'False Positive' 
            THEN TRUE 
            ELSE FALSE 
        END AS is_false_positive,
        
        -- Recovery Rate
        CASE 
            WHEN amount_recovered > 0 
            THEN amount_recovered 
            ELSE 0 
        END AS recovered_amount,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE alert_id IS NOT NULL
)

SELECT * FROM cleaned;
