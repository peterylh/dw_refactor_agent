-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_transactions;

INSERT INTO finance_analytics_dm.dws_transactions (
    transaction_id,
    transaction_key,
    customer_key,
    account_key,
    merchant_key,
    date_key,
    transaction_date,
    transaction_year,
    transaction_month,
    transaction_day,
    transaction_hour,
    day_of_week,
    is_weekend,
    is_late_night,
    transaction_type,
    transaction_direction,
    currency,
    channel,
    merchant_category,
    mcc_code,
    description,
    location_city,
    location_state,
    location_country,
    is_international,
    device_id,
    authorization_code,
    card_last_four,
    is_recurring,
    transaction_status,
    decline_reason,
    fraud_risk_category,
    transaction_amount,
    transaction_amount_abs,
    fraud_score,
    distance_from_home_km,
    merchant_risk_score,
    velocity_24h,
    amount_deviation_score,
    processing_time_ms,
    is_fraud_flag,
    is_high_value_flag,
    is_high_risk_flag,
    is_declined_flag,
    fraud_amount,
    declined_count,
    transaction_count,
    dbt_updated_at
)
WITH transaction_facts AS (
    SELECT
        t.transaction_id,
        
        -- Surrogate Keys (Dimension References)
        MD5(CONCAT_WS('||', COALESCE(CAST(t.transaction_id AS STRING), '_dbt_null_'))) AS transaction_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(t.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(t.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(t.merchant_id AS STRING), '_dbt_null_'))) AS merchant_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(t.transaction_date AS DATE) AS STRING), '_dbt_null_'))) AS date_key,
        
        -- Degenerate Dimensions (Transaction Attributes)
        t.transaction_date,
        t.transaction_year,
        t.transaction_month,
        t.transaction_day,
        t.transaction_hour,
        t.day_of_week,
        t.is_weekend,
        t.is_late_night,
        t.transaction_type,
        t.transaction_direction,
        t.currency,
        t.channel,
        t.merchant_category,
        t.mcc_code,
        t.description,
        t.location_city,
        t.location_state,
        t.location_country,
        t.is_international,
        t.device_id,
        t.authorization_code,
        t.card_last_four,
        t.is_recurring,
        t.transaction_status,
        t.decline_reason,
        t.fraud_risk_category,
        
        -- Measures (Facts)
        t.amount AS transaction_amount,
        t.amount_abs AS transaction_amount_abs,
        t.fraud_score,
        t.distance_from_home_km,
        t.merchant_risk_score,
        t.velocity_24h,
        t.amount_deviation_score,
        t.processing_time_ms,
        
        -- Flags (Boolean Facts)
        t.is_fraud AS is_fraud_flag,
        t.is_high_value AS is_high_value_flag,
        CASE WHEN t.fraud_risk_category = 'High Risk' THEN 1 ELSE 0 END AS is_high_risk_flag,
        CASE WHEN t.decline_reason IS NOT NULL THEN 1 ELSE 0 END AS is_declined_flag,
        
        -- Calculated Measures
        CASE WHEN t.is_fraud THEN t.amount_abs ELSE 0 END AS fraud_amount,
        CASE WHEN t.decline_reason IS NOT NULL THEN 1 ELSE 0 END AS declined_count,
        1 AS transaction_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_transactions t
    
)

SELECT * FROM transaction_facts;
