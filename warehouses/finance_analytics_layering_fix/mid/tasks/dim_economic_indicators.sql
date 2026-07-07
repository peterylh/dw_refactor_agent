-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_economic_indicators;

INSERT INTO finance_analytics_dm.dim_economic_indicators
WITH economic_enhanced AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(date AS STRING), '_dbt_null_'))) AS economic_indicator_key,
        date AS indicator_date,
        year,
        quarter,
        month,
        
        -- Economic Metrics
        gdp_growth_rate,
        unemployment_rate,
        inflation_rate,
        federal_funds_rate,
        sp500_index,
        vix_index,
        consumer_confidence_index,
        housing_price_index,
        `10yr_treasury_yield`,
        mortgage_rate_30yr,
        
        -- Economic Classifications
        economic_health,
        unemployment_level,
        market_volatility,
        
        -- Recession Indicator
        CASE 
            WHEN gdp_growth_rate < 0 THEN TRUE 
            ELSE FALSE 
        END AS is_recession,
        
        -- Interest Rate Environment
        CASE
            WHEN federal_funds_rate < 2 THEN 'Low Rate'
            WHEN federal_funds_rate < 4 THEN 'Normal Rate'
            ELSE 'High Rate'
        END AS rate_environment,
        
        -- Inflation Category
        CASE
            WHEN inflation_rate < 2 THEN 'Low Inflation'
            WHEN inflation_rate < 3 THEN 'Target Inflation'
            WHEN inflation_rate < 5 THEN 'Elevated Inflation'
            ELSE 'High Inflation'
        END AS inflation_category,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_economic_indicators
)

SELECT * FROM economic_enhanced;
