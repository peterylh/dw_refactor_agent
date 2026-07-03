-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_economic_indicators;

INSERT INTO finance_analytics_dm.dwd_economic_indicators
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_economic_indicators
),

cleaned AS (
    SELECT
        date,
        YEAR(date) AS year,
        QUARTER(date) AS quarter,
        MONTH(date) AS month,
        
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
        
        -- Economic Health Indicators
        CASE
            WHEN gdp_growth_rate >= 3 THEN 'Strong Growth'
            WHEN gdp_growth_rate >= 2 THEN 'Moderate Growth'
            WHEN gdp_growth_rate >= 0 THEN 'Slow Growth'
            ELSE 'Recession'
        END AS economic_health,
        
        CASE
            WHEN unemployment_rate < 4 THEN 'Low'
            WHEN unemployment_rate < 6 THEN 'Normal'
            ELSE 'High'
        END AS unemployment_level,
        
        CASE
            WHEN vix_index < 15 THEN 'Low Volatility'
            WHEN vix_index < 25 THEN 'Normal Volatility'
            ELSE 'High Volatility'
        END AS market_volatility,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE date IS NOT NULL
)

SELECT * FROM cleaned;
