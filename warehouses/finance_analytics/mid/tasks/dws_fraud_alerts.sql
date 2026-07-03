-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_fraud_alerts;

INSERT INTO finance_analytics_dm.dws_fraud_alerts
WITH fraud_alert_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(fa.alert_id AS STRING), '_dbt_null_'))) AS alert_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(fa.transaction_id AS STRING), '_dbt_null_'))) AS transaction_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(fa.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(fa.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(fa.alert_date AS DATE) AS STRING), '_dbt_null_'))) AS alert_date_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(fa.resolution_date AS DATE) AS STRING), '_dbt_null_'))) AS resolution_date_key,
        
        fa.alert_id,
        fa.alert_date,
        fa.alert_type,
        fa.alert_severity,
        fa.investigation_status,
        fa.resolution_date,
        fa.assigned_to,
        
        -- Measures
        fa.amount_recovered,
        fa.resolution_days,
        
        -- Flags
        CASE WHEN fa.is_resolved THEN 1 ELSE 0 END AS resolved_flag,
        CASE WHEN fa.is_confirmed_fraud THEN 1 ELSE 0 END AS confirmed_fraud_flag,
        CASE WHEN fa.is_false_positive THEN 1 ELSE 0 END AS false_positive_flag,
        
        -- Counts
        1 AS alert_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_fraud_alerts fa
)

SELECT * FROM fraud_alert_facts;
