DROP TABLE IF EXISTS finance_analytics_dm.dwd_customer_interactions;
-- table_id: 10cfb5e3-5d4d-463c-96a6-fb9bda23d77c
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_customer_interactions (
    -- column_id: fea17776-568d-4674-bee4-93b3f1fcfa8a
    interaction_id BIGINT NULL,
    -- column_id: fc3655c6-29ea-4a7f-abdc-dfc554cf80f0
    customer_id BIGINT NULL,
    -- column_id: c7a83ddd-2655-49dc-bf44-9b7b9e1d464c
    interaction_date DATETIME NULL,
    -- column_id: d05ba3a2-81d4-4429-8f2f-a14de51f8750
    interaction_year BIGINT NULL,
    -- column_id: d0fb005a-4164-45d0-a8bb-cecbb3f36cf7
    interaction_month BIGINT NULL,
    -- column_id: 9a19b632-2bc0-4108-ae0a-28658aedcdfe
    interaction_type STRING NULL,
    -- column_id: 827722b7-16b5-4c96-b601-c66159aa1016
    reason STRING NULL,
    -- column_id: 792b8411-3b00-4752-a8fe-b73dd093553b
    duration_minutes BIGINT NULL,
    -- column_id: d9ac7663-dca7-4569-8e98-bbbb9cd768bb
    duration_category STRING NULL,
    -- column_id: 95eda1ab-150a-411d-b441-74bd08401ffe
    sentiment_score DECIMAL(18,4) NULL,
    -- column_id: 6241609a-284f-46a8-9b92-40f489285def
    sentiment_category STRING NULL,
    -- column_id: 78064e0c-d39b-4655-9c59-0d418c2de1b6
    satisfaction_rating STRING NULL,
    -- column_id: 613b7032-4023-4d5f-9692-6e4ee719e6cc
    resolved STRING NULL,
    -- column_id: 7421bc9f-f600-475b-b35d-f9ddc2e482f3
    escalated STRING NULL,
    -- column_id: 76fae58c-9960-4c70-a535-5bdc625c2fd7
    agent_id STRING NULL,
    -- column_id: e76400e2-1ea2-4655-971c-700e934df71d
    notes STRING NULL,
    -- column_id: a4737649-482d-4d2f-a2e2-8bc485f43018
    issue_severity STRING NULL,
    -- column_id: 2986d293-6b89-47f2-b981-d6c644c61e60
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(interaction_id)
DISTRIBUTED BY HASH(interaction_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
