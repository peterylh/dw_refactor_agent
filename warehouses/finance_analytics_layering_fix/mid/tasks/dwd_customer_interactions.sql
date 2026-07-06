-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_customer_interactions;

INSERT INTO finance_analytics_dm.dwd_customer_interactions
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_customer_interactions
),

cleaned AS (
    SELECT
        interaction_id,
        customer_id,
        CAST(interaction_date AS DATETIME) AS interaction_date,
        YEAR(interaction_date) AS interaction_year,
        MONTH(interaction_date) AS interaction_month,
        
        interaction_type,
        reason,
        duration_minutes,
        
        -- Duration Categories
        CASE
            WHEN duration_minutes < 5 THEN 'Quick'
            WHEN duration_minutes < 15 THEN 'Standard'
            WHEN duration_minutes < 30 THEN 'Extended'
            ELSE 'Complex'
        END AS duration_category,
        
        -- Sentiment
        sentiment_score,
        CASE
            WHEN sentiment_score >= 0.5 THEN 'Positive'
            WHEN sentiment_score >= -0.2 THEN 'Neutral'
            ELSE 'Negative'
        END AS sentiment_category,
        
        satisfaction_rating,
        resolved,
        escalated,
        agent_id,
        notes,
        
        -- Issue Severity
        CASE
            WHEN escalated THEN 'High'
            WHEN NOT resolved THEN 'Medium'
            ELSE 'Low'
        END AS issue_severity,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE interaction_id IS NOT NULL
)

SELECT * FROM cleaned;
