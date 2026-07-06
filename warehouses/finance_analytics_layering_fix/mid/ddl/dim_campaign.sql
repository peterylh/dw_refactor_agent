DROP TABLE IF EXISTS finance_analytics_dm.dim_campaign;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_campaign (
    campaign_key CHAR(32) NULL,
    campaign_natural_key BIGINT NULL,
    campaign_name STRING NULL,
    campaign_type STRING NULL,
    start_date DATETIME NULL,
    end_date DATETIME NULL,
    target_segment STRING NULL,
    product_promoted STRING NULL,
    campaign_duration_days BIGINT NULL,
    campaign_status STRING NULL,
    roi_category STRING NULL,
    campaign_duration_category STRING NULL,
    channel_group STRING NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(campaign_key)
DISTRIBUTED BY HASH(campaign_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
