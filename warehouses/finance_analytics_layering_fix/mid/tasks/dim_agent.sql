-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_agent;

INSERT INTO finance_analytics_dm.dim_agent
WITH agent_list AS (
    SELECT DISTINCT
        agent_id
    FROM finance_analytics_dm.dwd_customer_interactions
    WHERE agent_id IS NOT NULL
),

agent_metrics AS (
    SELECT
        agent_id,
        COUNT(*) AS total_interactions,
        AVG(duration_minutes) AS avg_interaction_duration,
        AVG(satisfaction_rating) AS avg_satisfaction_rating,
        AVG(sentiment_score) AS avg_sentiment_score,
        CAST(SUM(CASE WHEN resolved THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) AS resolution_rate,
        CAST(SUM(CASE WHEN escalated THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) AS escalation_rate
    FROM finance_analytics_dm.dwd_customer_interactions
    WHERE agent_id IS NOT NULL
    GROUP BY agent_id
),

agent_enhanced AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(a.agent_id AS STRING), '_dbt_null_'))) AS agent_key,
        a.agent_id AS agent_natural_key,
        
        -- Performance Metrics
        COALESCE(m.total_interactions, 0) AS total_interactions,
        COALESCE(m.avg_interaction_duration, 0) AS avg_interaction_duration,
        COALESCE(m.avg_satisfaction_rating, 0) AS avg_satisfaction_rating,
        COALESCE(m.avg_sentiment_score, 0) AS avg_sentiment_score,
        COALESCE(m.resolution_rate, 0) AS resolution_rate,
        COALESCE(m.escalation_rate, 0) AS escalation_rate,
        
        -- Performance Classification
        CASE
            WHEN m.avg_satisfaction_rating >= 4.5 THEN 'Excellent'
            WHEN m.avg_satisfaction_rating >= 4.0 THEN 'Good'
            WHEN m.avg_satisfaction_rating >= 3.5 THEN 'Average'
            ELSE 'Needs Improvement'
        END AS performance_tier,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM agent_list a
    LEFT JOIN agent_metrics m ON a.agent_id = m.agent_id
)

SELECT * FROM agent_enhanced;
