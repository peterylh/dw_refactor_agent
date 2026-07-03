-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_customer_interactions;

INSERT INTO finance_analytics_dm.dws_customer_interactions
WITH interaction_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(ci.interaction_id AS STRING), '_dbt_null_'))) AS interaction_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ci.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(ci.interaction_date AS DATE) AS STRING), '_dbt_null_'))) AS interaction_date_key,
        
        ci.interaction_id,
        ci.interaction_date,
        ci.interaction_year,
        ci.interaction_month,
        ci.interaction_type,
        ci.reason,
        ci.duration_category,
        ci.sentiment_category,
        ci.issue_severity,
        ci.agent_id,
        
        -- Measures
        ci.duration_minutes,
        ci.sentiment_score,
        ci.satisfaction_rating,
        
        -- Flags
        CASE WHEN ci.resolved THEN 1 ELSE 0 END AS resolved_flag,
        CASE WHEN ci.escalated THEN 1 ELSE 0 END AS escalated_flag,
        CASE WHEN ci.sentiment_category = 'Positive' THEN 1 ELSE 0 END AS positive_sentiment_flag,
        CASE WHEN ci.sentiment_category = 'Negative' THEN 1 ELSE 0 END AS negative_sentiment_flag,
        
        -- Counts
        1 AS interaction_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_customer_interactions ci
)

SELECT * FROM interaction_facts;
