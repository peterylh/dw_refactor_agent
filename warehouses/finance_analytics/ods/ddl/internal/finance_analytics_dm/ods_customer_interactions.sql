DROP TABLE IF EXISTS finance_analytics_dm.ods_customer_interactions;
-- table_id: 8fde9fc0-adba-493d-aabf-d229953bb74d
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_customer_interactions (
    -- column_id: 7251369c-c77e-4a49-bb5d-0c5619ba445a
    interaction_id BIGINT NULL,
    -- column_id: 0da9ba91-e83d-4f80-beb3-f60366f87e63
    customer_id BIGINT NULL,
    -- column_id: 063b89af-c922-4a26-a707-36c28f3ab863
    interaction_date DATETIME NULL,
    -- column_id: 06e18192-acc8-4d7c-b6dd-4bf97a0d7c66
    interaction_type STRING NULL,
    -- column_id: 7967a769-b6f4-43ce-b5d4-62b90d0368d6
    reason STRING NULL,
    -- column_id: 6d27e504-5bba-4148-b269-27d3469bee6d
    duration_minutes BIGINT NULL,
    -- column_id: 096a06c3-5cfe-4bd8-b455-ad98db479055
    sentiment_score DECIMAL(18,4) NULL,
    -- column_id: da5693c6-afb3-404b-8ef8-04685aa0535a
    satisfaction_rating STRING NULL,
    -- column_id: 1222aa2f-077a-4ba7-bd7e-83f0c9d99af5
    resolved STRING NULL,
    -- column_id: 11ee04c6-fd29-4680-977a-40bd49d50bbb
    escalated STRING NULL,
    -- column_id: 695d1315-4544-4e02-8ac3-7439f6972d50
    agent_id STRING NULL,
    -- column_id: 1c2b671e-62d3-4824-807c-58189378cecb
    notes STRING NULL,
    -- column_id: 9a20ec52-fa2d-4297-a3a8-9a7ca85e60ec
    created_at DATETIME NULL,
    -- column_id: 7abb0ace-0bdc-43d6-b331-b13c40611a66
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(interaction_id)
DISTRIBUTED BY HASH(interaction_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
