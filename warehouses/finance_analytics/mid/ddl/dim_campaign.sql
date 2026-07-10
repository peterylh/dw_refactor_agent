DROP TABLE IF EXISTS finance_analytics_dm.dim_campaign;
-- table_id: d5cf0948-4a7c-4ad9-b65e-cbcbb8426d63
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_campaign (
    -- column_id: 6f3f5b67-9212-416f-af0e-2fdfda2b3f32
    campaign_key CHAR(32) NULL,
    -- column_id: cbd5cb95-09cf-4e9e-8a46-d7a423ac7789
    campaign_natural_key BIGINT NULL,
    -- column_id: f29b58aa-222a-4a82-8ab8-7d9503b8b1be
    campaign_name STRING NULL,
    -- column_id: 0a63dbaa-bbcf-4e90-9e20-1f5449228f87
    campaign_type STRING NULL,
    -- column_id: a0eaeb3e-0e58-4f19-bc1e-722a2c80b006
    start_date DATETIME NULL,
    -- column_id: 6419c197-4eeb-4178-a59f-dd92dfd0adce
    end_date DATETIME NULL,
    -- column_id: 52419b7e-abb3-454a-8042-fbeaa2c674fa
    target_segment STRING NULL,
    -- column_id: 04024bb3-2d47-4075-93e2-de630c0fb803
    product_promoted STRING NULL,
    -- column_id: 0407955c-459a-4b6b-8df7-752478536f8f
    campaign_duration_days BIGINT NULL,
    -- column_id: 622a7f8f-bd41-4711-9d59-56d60eda9968
    campaign_status STRING NULL,
    -- column_id: c978a0fb-8a17-4def-9f5d-aaede321b002
    roi_category STRING NULL,
    -- column_id: d4cda91f-4748-47ed-b400-2ea881b07a4b
    campaign_duration_category STRING NULL,
    -- column_id: e6a28b48-55a2-44ee-a4c5-0dc81240d76e
    channel_group STRING NULL,
    -- column_id: 261f4a6e-aa01-4a99-9175-8220d5e3f2d1
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_key)
DISTRIBUTED BY HASH(campaign_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
