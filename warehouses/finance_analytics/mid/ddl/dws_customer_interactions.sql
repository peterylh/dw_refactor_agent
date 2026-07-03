DROP TABLE IF EXISTS finance_analytics_dm.dws_customer_interactions;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_customer_interactions (
    interaction_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    interaction_date_key CHAR(32) NULL,
    interaction_id BIGINT NULL,
    interaction_date DATETIME NULL,
    interaction_year BIGINT NULL,
    interaction_month BIGINT NULL,
    interaction_type STRING NULL,
    reason STRING NULL,
    duration_category STRING NULL,
    sentiment_category STRING NULL,
    issue_severity STRING NULL,
    agent_id STRING NULL,
    duration_minutes BIGINT NULL,
    sentiment_score DECIMAL(18,4) NULL,
    satisfaction_rating STRING NULL,
    resolved_flag BOOLEAN NULL,
    escalated_flag BOOLEAN NULL,
    positive_sentiment_flag BOOLEAN NULL,
    negative_sentiment_flag BOOLEAN NULL,
    interaction_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(interaction_key)
DISTRIBUTED BY HASH(interaction_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
