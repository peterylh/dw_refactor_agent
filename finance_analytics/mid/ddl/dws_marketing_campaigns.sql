DROP TABLE IF EXISTS finance_analytics_dm.dws_marketing_campaigns;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_marketing_campaigns (
    campaign_key CHAR(32) NULL,
    start_date_key CHAR(32) NULL,
    end_date_key CHAR(32) NULL,
    campaign_id BIGINT NULL,
    campaign_name STRING NULL,
    campaign_type STRING NULL,
    start_date DATETIME NULL,
    end_date DATETIME NULL,
    target_segment STRING NULL,
    product_promoted STRING NULL,
    campaign_status STRING NULL,
    roi_category STRING NULL,
    campaign_duration_days BIGINT NULL,
    budget STRING NULL,
    cost_per_acquisition DECIMAL(18,4) NULL,
    roi STRING NULL,
    impressions STRING NULL,
    clicks STRING NULL,
    conversions STRING NULL,
    click_through_rate DECIMAL(18,4) NULL,
    conversion_rate DECIMAL(18,4) NULL,
    conversions_per_1k_budget STRING NULL,
    cost_per_1k_impressions DECIMAL(18,4) NULL,
    estimated_revenue STRING NULL,
    profitable_flag BOOLEAN NULL,
    highly_profitable_flag BOOLEAN NULL,
    high_engagement_flag BOOLEAN NULL,
    high_conversion_flag BOOLEAN NULL,
    active_campaign_flag BOOLEAN NULL,
    completed_campaign_flag BOOLEAN NULL,
    campaign_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_key)
DISTRIBUTED BY HASH(campaign_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
