DROP TABLE IF EXISTS finance_analytics_dm.dws_customer_interactions;
-- table_id: 433693e8-fa5c-4b9a-8512-b3568ca0413a
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_customer_interactions (
    -- column_id: 21cd58c4-29dd-4f6f-8188-bdec78bf54ab
    interaction_key CHAR(32) NULL,
    -- column_id: 24791a7d-2991-4fb6-83b1-6b21b3a1d9b9
    customer_key CHAR(32) NULL,
    -- column_id: cc7ec378-35c4-4b25-85dc-12fbabbc7f2b
    interaction_date_key CHAR(32) NULL,
    -- column_id: 993ae728-a61e-49cf-a6c4-919ff46055db
    interaction_id BIGINT NULL,
    -- column_id: 332427b9-438d-495c-8cf1-3fe6ef8e6c71
    interaction_date DATETIME NULL,
    -- column_id: 67e16eed-67f0-4766-8abe-d10808268529
    interaction_year BIGINT NULL,
    -- column_id: dfbdfcf6-fdf6-4721-88e1-857febb1073c
    interaction_month BIGINT NULL,
    -- column_id: 20550011-f024-469b-ae8e-bdc271c15f64
    interaction_type STRING NULL,
    -- column_id: aa3b50ca-35d3-40db-88b6-622988a247c7
    reason STRING NULL,
    -- column_id: d3101362-f652-4e1b-bd37-8e5e0b9ac82a
    duration_category STRING NULL,
    -- column_id: 92f1d35b-07f7-45c5-9781-bf502a81fbcb
    sentiment_category STRING NULL,
    -- column_id: 62e70314-6ea2-446c-ba1f-697cd44e23db
    issue_severity STRING NULL,
    -- column_id: 8239de52-09d1-463e-8075-5f0a1c845745
    agent_id STRING NULL,
    -- column_id: 7c323039-6262-438b-ab39-88fc3ed8ef63
    duration_minutes BIGINT NULL,
    -- column_id: 7e47bb4a-4192-4057-aa92-fe557dbd16c9
    sentiment_score DECIMAL(18,4) NULL,
    -- column_id: 3ff4949a-a3da-495f-84d9-acd86647cd6a
    satisfaction_rating STRING NULL,
    -- column_id: 0d3748ec-8de4-489d-a75f-b239b77b2d47
    resolved_flag BOOLEAN NULL,
    -- column_id: 5f843ecb-8c50-449d-a12a-42277f0528ed
    escalated_flag BOOLEAN NULL,
    -- column_id: cb45339f-3b38-4d3a-b55c-83fcae1a23ff
    positive_sentiment_flag BOOLEAN NULL,
    -- column_id: a5be36d2-bf1c-4042-934e-1393472a989c
    negative_sentiment_flag BOOLEAN NULL,
    -- column_id: 17c94935-3bed-4cb1-ac99-2c69045ed896
    interaction_count BIGINT NULL,
    -- column_id: 7e98e306-5399-4ffe-89ac-cd63269e4ce5
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(interaction_key)
DISTRIBUTED BY HASH(interaction_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
