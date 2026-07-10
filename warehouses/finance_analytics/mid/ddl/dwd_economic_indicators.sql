DROP TABLE IF EXISTS finance_analytics_dm.dwd_economic_indicators;
-- table_id: 73056d30-3b96-4fca-98dc-130c54ad12b2
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_economic_indicators (
    -- column_id: 7f11d5dd-4087-431a-817c-d1fbb3eb33f5
    date DATETIME NULL,
    -- column_id: 28f8ca7b-f37b-4ee4-8e0b-38d6fb84bf04
    year BIGINT NULL,
    -- column_id: 3c518b8b-cbd0-4f34-87b5-103a3e6882df
    quarter BIGINT NULL,
    -- column_id: 5ecc633a-e0d4-4e58-9638-d1846c3a0f20
    month BIGINT NULL,
    -- column_id: b2dae107-87d6-4042-9aab-3169c6ad1536
    gdp_growth_rate DECIMAL(18,4) NULL,
    -- column_id: 7a954c31-d5dc-4fbf-be91-2615961ea6ac
    unemployment_rate DECIMAL(18,4) NULL,
    -- column_id: b68f18d0-b580-4619-bef0-f392a9922e35
    inflation_rate DECIMAL(18,4) NULL,
    -- column_id: 5ce8fb0d-934b-4e66-bb38-911ef4fe3f91
    federal_funds_rate DECIMAL(18,4) NULL,
    -- column_id: 66ece921-3f01-4a3a-9941-0eeb14248286
    sp500_index STRING NULL,
    -- column_id: d002a660-4a5c-45f1-b51d-47ea0d9ac61e
    vix_index STRING NULL,
    -- column_id: 655b96da-3b86-4964-82b9-6332e90b1282
    consumer_confidence_index STRING NULL,
    -- column_id: 012eea24-b86c-4c4e-b167-a13677ec5fba
    housing_price_index DECIMAL(18,4) NULL,
    -- column_id: 05220a2c-fc36-4423-a20a-22c15e1a8054
    `10yr_treasury_yield` DECIMAL(18,4) NULL,
    -- column_id: 64f69e43-29e6-459f-b0f4-1ee82d663e5a
    mortgage_rate_30yr DECIMAL(18,4) NULL,
    -- column_id: bf5b2539-a783-4c2f-aa9b-f1b28e4d942f
    economic_health STRING NULL,
    -- column_id: 5b9c5843-10cc-47da-975b-91f8ce641950
    unemployment_level STRING NULL,
    -- column_id: 2d1855a1-fd3f-47cb-97f5-faea81f7ca70
    market_volatility STRING NULL,
    -- column_id: 3644fcb4-ef66-42bb-b9a0-285cb2ef65bb
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(date)
DISTRIBUTED BY HASH(date) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
