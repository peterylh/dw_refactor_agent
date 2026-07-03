-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_transactions;

INSERT INTO finance_analytics_dm.dwd_transactions
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_transactions
    
),

cleaned AS (
    SELECT
        -- Primary Keys
        transaction_id,
        account_id,
        customer_id,
        merchant_id,
        
        -- Transaction Details
        transaction_date,
        YEAR(transaction_date) AS transaction_year,
        MONTH(transaction_date) AS transaction_month,
        DAY(transaction_date) AS transaction_day,
        HOUR(transaction_date) AS transaction_hour,
        (DAYOFWEEK(transaction_date) - 1) AS day_of_week,
        
        -- Date Flags
        CASE WHEN (DAYOFWEEK(transaction_date) - 1) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend,
        CASE WHEN (HOUR(transaction_date) >= 22 OR HOUR(transaction_date) <= 6) THEN TRUE ELSE FALSE END AS is_late_night,
        
        transaction_type,
        amount,
        ABS(amount) AS amount_abs,
        CASE WHEN amount < 0 THEN 'Debit' ELSE 'Credit' END AS transaction_direction,
        currency,
        channel,
        
        -- Merchant Information
        merchant_category,
        mcc_code,
        TRIM(description) AS description,
        
        -- Fraud Detection
        is_fraud,
        fraud_score,
        
        -- Enhanced Fraud Indicators
        CASE
            WHEN fraud_score >= 0.7 THEN 'High Risk'
            WHEN fraud_score >= 0.4 THEN 'Medium Risk'
            ELSE 'Low Risk'
        END AS fraud_risk_category,
        
        CASE
            WHEN ABS(amount) > 10000 THEN TRUE
            ELSE FALSE
        END AS is_high_value,
        
        -- Location
        location_city,
        location_state,
        location_country,
        latitude,
        longitude,
        is_international,
        
        -- Device & Security
        device_id,
        ip_address,
        authorization_code,
        card_last_four,
        
        -- Behavioral Features
        is_recurring,
        hour_of_day,
        is_weekend AS weekend_flag,
        distance_from_home_km,
        merchant_risk_score,
        velocity_24h,
        amount_deviation_score,
        processing_time_ms,
        decline_reason,
        
        -- Status Flag
        CASE
            WHEN decline_reason IS NOT NULL THEN 'Declined'
            WHEN is_fraud THEN 'Fraud'
            ELSE 'Approved'
        END AS transaction_status,
        
        -- Metadata
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE transaction_id IS NOT NULL
      AND account_id IS NOT NULL
)

SELECT * FROM cleaned;
