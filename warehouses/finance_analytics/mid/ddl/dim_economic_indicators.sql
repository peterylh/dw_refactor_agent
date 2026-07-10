DROP TABLE IF EXISTS finance_analytics_dm.dim_economic_indicators;
-- table_id: 799ddd44-b81d-4050-8e36-d1591461e691
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_economic_indicators (
    -- column_id: 5b3d8e05-f83a-4424-81d6-0e9a96b8ebf4
    economic_indicator_key CHAR(32) NULL,
    -- column_id: 684bb833-9467-4fa5-9d13-d891788e56d0
    indicator_date DATETIME NULL,
    -- column_id: 64c2200c-a981-45ae-9da3-972919ee4e5e
    year BIGINT NULL,
    -- column_id: b86b1b58-5cc0-437e-8b74-fa28e6b8d11c
    quarter BIGINT NULL,
    -- column_id: c93475c7-feff-4a42-bf69-17c76c9e8a37
    month BIGINT NULL,
    -- column_id: b56af3a1-15a2-4860-bc4f-d6f5c9a3787e
    gdp_growth_rate DECIMAL(18,4) NULL,
    -- column_id: 84f90296-7bb7-4a12-80c1-37c058eecfc3
    unemployment_rate DECIMAL(18,4) NULL,
    -- column_id: 27c78058-532e-4bca-92f4-6d2453e6f134
    inflation_rate DECIMAL(18,4) NULL,
    -- column_id: 3c77142f-7f49-4648-8c87-8428bdb65946
    federal_funds_rate DECIMAL(18,4) NULL,
    -- column_id: 9d014ab5-8a7e-4cbf-924e-42e77aeb5087
    sp500_index STRING NULL,
    -- column_id: f4f8f13b-eb2d-4ba4-bbfe-e7e945ba8945
    vix_index STRING NULL,
    -- column_id: 74b98ba1-6604-4f63-a248-f852449f27ca
    consumer_confidence_index STRING NULL,
    -- column_id: cef853cc-fc58-4c94-b13b-77f4ff413374
    housing_price_index DECIMAL(18,4) NULL,
    -- column_id: fc45bf67-ddeb-43cb-88b9-08a06cc08fad
    `10yr_treasury_yield` DECIMAL(18,4) NULL,
    -- column_id: 499ef851-3417-476c-ace7-bb38c73162c6
    mortgage_rate_30yr DECIMAL(18,4) NULL,
    -- column_id: eb66f608-fcfb-45c5-a687-1b61f55506b2
    economic_health STRING NULL,
    -- column_id: 1cb7a975-0705-4526-8860-b60ab570c198
    unemployment_level STRING NULL,
    -- column_id: 6ca0729b-d1bc-47f4-b2fd-90483074ebbb
    market_volatility STRING NULL,
    -- column_id: 7c8116fd-5172-4eb0-ac79-c20d82c13e13
    is_recession BOOLEAN NULL,
    -- column_id: c3f8dfcb-2ccd-4c81-81a5-59aa44946b2c
    rate_environment DECIMAL(18,4) NULL,
    -- column_id: 7421539c-3c62-4861-a4fe-1df56380f787
    inflation_category STRING NULL,
    -- column_id: e3fd1578-448f-459d-9bce-bfcbf8ed0257
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(economic_indicator_key)
DISTRIBUTED BY HASH(economic_indicator_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
