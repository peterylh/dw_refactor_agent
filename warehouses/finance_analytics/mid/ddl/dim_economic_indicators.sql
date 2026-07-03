DROP TABLE IF EXISTS finance_analytics_dm.dim_economic_indicators;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_economic_indicators (
    economic_indicator_key CHAR(32) NULL,
    indicator_date DATETIME NULL,
    year BIGINT NULL,
    quarter BIGINT NULL,
    month BIGINT NULL,
    gdp_growth_rate DECIMAL(18,4) NULL,
    unemployment_rate DECIMAL(18,4) NULL,
    inflation_rate DECIMAL(18,4) NULL,
    federal_funds_rate DECIMAL(18,4) NULL,
    sp500_index STRING NULL,
    vix_index STRING NULL,
    consumer_confidence_index STRING NULL,
    housing_price_index DECIMAL(18,4) NULL,
    `10yr_treasury_yield` DECIMAL(18,4) NULL,
    mortgage_rate_30yr DECIMAL(18,4) NULL,
    economic_health STRING NULL,
    unemployment_level STRING NULL,
    market_volatility STRING NULL,
    is_recession BOOLEAN NULL,
    rate_environment DECIMAL(18,4) NULL,
    inflation_category STRING NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(economic_indicator_key)
DISTRIBUTED BY HASH(economic_indicator_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
