-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_customer_segments_history;

INSERT INTO finance_analytics_dm.dwd_customer_segments_history
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_customer_segments_history
),

cleaned AS (
    SELECT
        -- Primary Keys
        segment_history_id,
        customer_id,
        
        -- Effective Period (SCD Type 2)
        effective_date,
        end_date,
        is_current,
        
        -- Segment Values
        customer_segment,
        previous_segment,
        loyalty_tier,
        previous_tier,
        risk_segment,
        previous_risk,
        
        -- Change Details
        change_type,
        TRIM(change_reason) AS change_reason,
        triggered_by,
        
        -- Customer Metrics at Change
        total_accounts,
        ROUND(CAST(total_balance AS DECIMAL(15,2)), 2) AS total_balance,
        avg_monthly_transactions,
        products_held,
        ROUND(CAST(customer_lifetime_value AS DECIMAL(15,2)), 2) AS customer_lifetime_value,
        tenure_days,
        credit_score,
        ROUND(CAST(annual_income AS DECIMAL(12,2)), 2) AS annual_income,
        
        -- Engagement Metrics
        last_interaction_days,
        ROUND(CAST(digital_engagement_score AS DECIMAL(5,3)), 3) AS digital_engagement_score,
        branch_visits_last_90d,
        online_logins_last_90d,
        
        -- Flags
        eligible_for_premium,
        churn_risk,
        cross_sell_opportunity,
        
        -- Metadata
        TRIM(notes) AS notes,
        TRIM(updated_by) AS updated_by,
        CURRENT_TIMESTAMP AS created_at
        
    FROM source
    WHERE segment_history_id IS NOT NULL
      AND customer_id IS NOT NULL
)

SELECT * FROM cleaned;
