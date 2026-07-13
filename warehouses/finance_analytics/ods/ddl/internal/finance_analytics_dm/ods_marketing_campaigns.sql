DROP TABLE IF EXISTS finance_analytics_dm.ods_marketing_campaigns;
-- table_id: ab1fa0fd-5f7a-49b5-9793-8b310bdfd5de
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_marketing_campaigns (
    -- column_id: 534e727c-b865-4992-ad46-06b311c42053
    campaign_id BIGINT NULL,
    -- column_id: 8d99ecf0-8b8f-492a-a03a-407f7a79741e
    campaign_name STRING NULL,
    -- column_id: 91039415-98de-4496-9156-69b72201b720
    campaign_type STRING NULL,
    -- column_id: 9bd458dd-ddd5-422b-ad85-dae5559afc28
    start_date DATETIME NULL,
    -- column_id: c556c074-c4ee-4261-b3b7-c5c9f4975ac0
    end_date DATETIME NULL,
    -- column_id: 06c3cbac-0129-404f-ad99-7cdd493d7088
    target_segment STRING NULL,
    -- column_id: ce63c475-2306-40db-ac89-e430ddc7d95d
    budget STRING NULL,
    -- column_id: f6b26b3b-d7d9-4280-97eb-a22e48ce048b
    impressions STRING NULL,
    -- column_id: 91b101f7-fc70-4e78-8141-d8fef3593663
    clicks STRING NULL,
    -- column_id: 5b22d245-8f44-4fcd-a0ff-a8ff2f35162e
    conversions STRING NULL,
    -- column_id: 318a4fa9-2fc6-40f5-820c-1d06fa7fbfde
    cost_per_acquisition DECIMAL(18,4) NULL,
    -- column_id: e55f00b0-fe39-4ddb-bab4-c23231e25314
    roi STRING NULL,
    -- column_id: 73c8fae9-b3f5-4ee7-a2c9-495ac24ca317
    product_promoted STRING NULL,
    -- column_id: d7df9842-667c-468b-8b32-4cdef1d2e2ec
    created_at DATETIME NULL,
    -- column_id: bb21a961-76e4-4340-a3b4-82f4cbd6f0e6
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_id)
DISTRIBUTED BY HASH(campaign_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
