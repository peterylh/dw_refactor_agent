-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_marketing_campaigns;

INSERT INTO finance_analytics_dm.dwd_marketing_campaigns
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_marketing_campaigns
),

cleaned AS (
    SELECT
        campaign_id,
        campaign_name,
        campaign_type,
        CAST(start_date AS DATETIME) as start_date,
        CAST(end_date AS DATETIME) as end_date,
        target_segment,
        budget,
        impressions,
        clicks,
        conversions,
        cost_per_acquisition,
        roi,
        product_promoted,
        
        -- Campaign Duration
        DAY((end_date - start_date)) AS campaign_duration_days,
        
        -- Performance Metrics
        CASE 
            WHEN impressions > 0 
            THEN ROUND((CAST(clicks AS DECIMAL(18,4)) / impressions * 100), 2) 
            ELSE 0 
        END AS click_through_rate,
        
        CASE 
            WHEN clicks > 0 
            THEN ROUND((CAST(conversions AS DECIMAL(18,4)) / clicks * 100), 2) 
            ELSE 0 
        END AS conversion_rate,
        
        -- ROI Category
        CASE
            WHEN roi >= 2.0 THEN 'Excellent'
            WHEN roi >= 1.0 THEN 'Good'
            WHEN roi >= 0 THEN 'Break Even'
            ELSE 'Loss'
        END AS roi_category,
        
        -- Campaign Status
        CASE
            WHEN CURRENT_DATE < start_date THEN 'Scheduled'
            WHEN CURRENT_DATE BETWEEN start_date AND end_date THEN 'Active'
            ELSE 'Completed'
        END AS campaign_status,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE campaign_id IS NOT NULL
)

SELECT * FROM cleaned;
