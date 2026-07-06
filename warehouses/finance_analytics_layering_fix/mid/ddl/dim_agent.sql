DROP TABLE IF EXISTS finance_analytics_dm.dim_agent;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_agent (
    agent_key CHAR(32) NULL,
    agent_natural_key BIGINT NULL,
    total_interactions BIGINT NULL,
    avg_interaction_duration DECIMAL(18,4) NULL,
    avg_satisfaction_rating DECIMAL(18,4) NULL,
    avg_sentiment_score DECIMAL(18,4) NULL,
    resolution_rate DECIMAL(18,4) NULL,
    escalation_rate DECIMAL(18,4) NULL,
    performance_tier STRING NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(agent_key)
DISTRIBUTED BY HASH(agent_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
