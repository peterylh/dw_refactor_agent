DROP TABLE IF EXISTS finance_analytics_dm.dws_marketing_campaigns;
-- table_id: fb1c536d-4663-4160-8545-5abb9c5c93e4
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_marketing_campaigns (
    -- column_id: 3ae24c49-9b91-4e62-922e-9aac5411e208
    campaign_key CHAR(32) NULL,
    -- column_id: 8ecfb8da-3754-4e2f-9a19-ab8d1b3076be
    start_date_key CHAR(32) NULL,
    -- column_id: 1d1415bb-ab4c-4443-be4a-8ddca09fd8db
    end_date_key CHAR(32) NULL,
    -- column_id: 4df26c74-a962-4361-aa40-37ff2c3e0442
    campaign_id BIGINT NULL,
    -- column_id: ab609dd7-aa6b-4bf2-80c3-038fbd07e39c
    campaign_name STRING NULL,
    -- column_id: 7d4a0aae-57c5-4e36-8b05-8c964bba1a00
    campaign_type STRING NULL,
    -- column_id: ea2d04a6-de60-4614-af82-7447b0b39312
    start_date DATETIME NULL,
    -- column_id: 86a89d88-f3ba-4055-b7a2-0b5d86279fb7
    end_date DATETIME NULL,
    -- column_id: 68860a66-2f94-4a3e-b18d-0d05867d4539
    target_segment STRING NULL,
    -- column_id: cea561c1-ebfd-4791-82d4-a08ea26c466a
    product_promoted STRING NULL,
    -- column_id: 13280535-6379-4608-b2b0-52d354edd9bb
    campaign_status STRING NULL,
    -- column_id: 35d84d5a-f424-496f-8a0c-e6cb020f04bc
    roi_category STRING NULL,
    -- column_id: 50d84d32-1983-4dd9-ba9a-8c7cbeada15e
    campaign_duration_days BIGINT NULL,
    -- column_id: 0a9d8826-8af8-4a42-9e1c-970648850ae9
    budget STRING NULL,
    -- column_id: 8d524ccd-44ad-4374-b2cc-102f4cdac7f0
    cost_per_acquisition DECIMAL(18,4) NULL,
    -- column_id: 28c5c5e6-1051-4085-b87c-3c7eba6c4de1
    roi STRING NULL,
    -- column_id: 4c7ca4a9-3aca-4343-9750-352c83a47064
    impressions STRING NULL,
    -- column_id: deb7fd5d-f3a4-4c46-96e6-43d8f86d26bd
    clicks STRING NULL,
    -- column_id: 86355e6c-59b2-499a-9dce-36706e135470
    conversions STRING NULL,
    -- column_id: 73d688a7-d6d4-4315-a514-9002d9b3e983
    click_through_rate DECIMAL(18,4) NULL,
    -- column_id: dd7a907b-2f75-441a-82b6-bb03badc819b
    conversion_rate DECIMAL(18,4) NULL,
    -- column_id: fa400470-961b-48ad-b282-a69e1223d1e4
    conversions_per_1k_budget STRING NULL,
    -- column_id: e9b86a09-6786-4066-9ce1-bf50e84afeb9
    cost_per_1k_impressions DECIMAL(18,4) NULL,
    -- column_id: 8cddf433-a10c-4aee-ade3-e435ff5905ed
    estimated_revenue STRING NULL,
    -- column_id: df07328b-2dc3-4737-9c80-6c3cda35e2b2
    profitable_flag BOOLEAN NULL,
    -- column_id: 0b43e312-4245-4173-987f-95b26c17268d
    highly_profitable_flag BOOLEAN NULL,
    -- column_id: e7cf7251-ccce-44a4-a790-63ba84783441
    high_engagement_flag BOOLEAN NULL,
    -- column_id: d22288c8-2072-4570-a974-65ab0f72d40a
    high_conversion_flag BOOLEAN NULL,
    -- column_id: 19a1a0f1-77b9-4ee1-a45c-0ab236ed6e94
    active_campaign_flag BOOLEAN NULL,
    -- column_id: 3179a2dc-4157-4233-86ea-9a9a0d65c2df
    completed_campaign_flag BOOLEAN NULL,
    -- column_id: 638363ba-0e4c-4158-a505-cdf2d71021c6
    campaign_count BIGINT NULL,
    -- column_id: 667b9850-62ee-4642-b0b6-c29e27b2a1e8
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_key)
DISTRIBUTED BY HASH(campaign_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
