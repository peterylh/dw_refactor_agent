DROP TABLE IF EXISTS finance_analytics_dm.dwd_customer_interactions;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_customer_interactions (
    interaction_id BIGINT NULL,
    customer_id BIGINT NULL,
    interaction_date DATETIME NULL,
    interaction_year BIGINT NULL,
    interaction_month BIGINT NULL,
    interaction_type STRING NULL,
    reason STRING NULL,
    duration_minutes BIGINT NULL,
    duration_category STRING NULL,
    sentiment_score DECIMAL(18,4) NULL,
    sentiment_category STRING NULL,
    satisfaction_rating STRING NULL,
    resolved STRING NULL,
    escalated STRING NULL,
    agent_id STRING NULL,
    notes STRING NULL,
    issue_severity STRING NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(interaction_id)
DISTRIBUTED BY HASH(interaction_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
