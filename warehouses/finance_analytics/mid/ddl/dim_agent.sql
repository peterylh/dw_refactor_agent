DROP TABLE IF EXISTS finance_analytics_dm.dim_agent;
-- table_id: 2c612621-df1b-481c-bbe9-44cd93d42fce
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_agent (
    -- column_id: bbbdfcaa-550a-4a2f-9097-24e440218d00
    agent_key CHAR(32) NULL,
    -- column_id: f538a60c-781f-4c54-af89-7f0bac86b9ff
    agent_natural_key BIGINT NULL,
    -- column_id: 3027659b-58b9-4ae2-8131-b9730712ca9d
    total_interactions BIGINT NULL,
    -- column_id: c7c9f39e-77e5-4a94-8e28-8df3b832e41d
    avg_interaction_duration DECIMAL(18,4) NULL,
    -- column_id: b651e8c4-a778-4116-897e-9ee7ff284e2a
    avg_satisfaction_rating DECIMAL(18,4) NULL,
    -- column_id: 40a6e5ff-65ea-4ae2-9c73-f29ebe103e47
    avg_sentiment_score DECIMAL(18,4) NULL,
    -- column_id: 342fe070-1065-4dd3-a836-8223ebc3fce7
    resolution_rate DECIMAL(18,4) NULL,
    -- column_id: 99f11710-2cd6-45a2-8ad4-17f659a82989
    escalation_rate DECIMAL(18,4) NULL,
    -- column_id: e26fc8a0-9e51-4fa8-8255-8adb17672f2c
    performance_tier STRING NULL,
    -- column_id: 703a8863-3d24-4ea1-a8fc-a21e7dee0c33
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(agent_key)
DISTRIBUTED BY HASH(agent_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
