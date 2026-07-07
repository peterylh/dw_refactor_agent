-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_campaign;

INSERT INTO finance_analytics_dm.dim_campaign
WITH campaign_enhanced AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(campaign_id AS STRING), '_dbt_null_'))) AS campaign_key,
        campaign_id AS campaign_natural_key,
        campaign_name,
        campaign_type,
        start_date,
        end_date,
        target_segment,
        product_promoted,
        campaign_duration_days,
        campaign_status,
        roi_category,
        
        -- Campaign Period Classification
        CASE
            WHEN campaign_duration_days < 7 THEN 'Short (< 1 week)'
            WHEN campaign_duration_days < 30 THEN 'Medium (1-4 weeks)'
            WHEN campaign_duration_days < 90 THEN 'Long (1-3 months)'
            ELSE 'Extended (3+ months)'
        END AS campaign_duration_category,
        
        -- Channel Classification
        CASE
            WHEN campaign_type IN ('Email', 'SMS', 'Push Notification') THEN 'Digital Direct'
            WHEN campaign_type IN ('Social Media', 'Display Ads', 'Search Ads') THEN 'Digital Advertising'
            WHEN campaign_type IN ('Direct Mail', 'Print', 'TV', 'Radio') THEN 'Traditional Media'
            ELSE 'Other'
        END AS channel_group,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_marketing_campaigns
)

SELECT * FROM campaign_enhanced;
