DROP TABLE IF EXISTS finance_analytics_dm.ods_marketing_campaigns;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_marketing_campaigns (
    campaign_id BIGINT NULL,
    campaign_name STRING NULL,
    campaign_type STRING NULL,
    start_date DATETIME NULL,
    end_date DATETIME NULL,
    target_segment STRING NULL,
    budget STRING NULL,
    impressions STRING NULL,
    clicks STRING NULL,
    conversions STRING NULL,
    cost_per_acquisition DECIMAL(18,4) NULL,
    roi STRING NULL,
    product_promoted STRING NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_id)
DISTRIBUTED BY HASH(campaign_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
