DROP TABLE IF EXISTS finance_analytics_dm.ods_economic_indicators;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_economic_indicators (
    date DATETIME NULL,
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
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(date)
DISTRIBUTED BY HASH(date) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
