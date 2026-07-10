DROP TABLE IF EXISTS finance_analytics_dm.dwd_marketing_campaigns;
-- table_id: 4f077680-a7a6-42b9-8cf8-624b6db97f07
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_marketing_campaigns (
    -- column_id: 8998a56f-df64-4b34-b353-688c11284457
    campaign_id BIGINT NULL,
    -- column_id: a004018a-db5c-411a-aaf4-b9ce3d635af1
    campaign_name STRING NULL,
    -- column_id: 376e6a7b-aa6d-41f5-973f-801795520573
    campaign_type STRING NULL,
    -- column_id: 278cdf8b-3c38-4bab-a115-0976f1c85e89
    start_date DATETIME NULL,
    -- column_id: dc13d206-e90c-4b82-b145-0fea749fd105
    end_date DATETIME NULL,
    -- column_id: a640a9a2-bc07-41c4-a973-d6cb1b572b16
    target_segment STRING NULL,
    -- column_id: 1135ba8b-4a8e-4d04-b714-f53d235c914e
    budget STRING NULL,
    -- column_id: f708626c-605f-44b8-939b-f6d16006a8d5
    impressions STRING NULL,
    -- column_id: f55e636e-4ce7-4278-abbd-cc7698b153fb
    clicks STRING NULL,
    -- column_id: 6d2ce957-1490-446e-8bc4-3432bdff2b5d
    conversions STRING NULL,
    -- column_id: b272c04d-7c0c-4acd-aed2-4b82069b0e0e
    cost_per_acquisition DECIMAL(18,4) NULL,
    -- column_id: dce32e6f-25db-496a-a96c-38fddb34cbea
    roi STRING NULL,
    -- column_id: 91b31582-53e1-4c44-9d38-a77c02b5a2e6
    product_promoted STRING NULL,
    -- column_id: 0297f08b-30cc-4f13-a98a-81d9d2c3b5bd
    campaign_duration_days BIGINT NULL,
    -- column_id: c9c38b0e-30ef-4fc1-8353-e65c41d266b3
    click_through_rate DECIMAL(18,4) NULL,
    -- column_id: 0e9b849e-dc0f-4a92-8570-7c7e6b5123d7
    conversion_rate DECIMAL(18,4) NULL,
    -- column_id: 37d8b9aa-3bcd-47dc-a085-90ef876930c9
    roi_category STRING NULL,
    -- column_id: 431c2e9a-8511-47fa-8aef-5385a2a84091
    campaign_status STRING NULL,
    -- column_id: 92abb94f-7cb3-4474-9fdb-f8b6b85a43ba
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_id)
DISTRIBUTED BY HASH(campaign_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
