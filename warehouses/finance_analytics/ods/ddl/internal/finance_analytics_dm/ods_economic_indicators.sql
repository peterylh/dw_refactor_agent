DROP TABLE IF EXISTS finance_analytics_dm.ods_economic_indicators;
-- table_id: 9536540c-31dd-43db-8282-336e3484a24e
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_economic_indicators (
    -- column_id: 7ff14351-566c-4f1b-a4ec-6128b3bec262
    date DATETIME NULL,
    -- column_id: 5721a775-3ab0-4a37-8a61-301f2fbb30f0
    gdp_growth_rate DECIMAL(18,4) NULL,
    -- column_id: efb3c58f-7083-46c0-9d81-75d4bd0bf1f9
    unemployment_rate DECIMAL(18,4) NULL,
    -- column_id: efdc3087-9860-471c-b4da-24018332a110
    inflation_rate DECIMAL(18,4) NULL,
    -- column_id: 3db00f54-95a1-41fb-be18-915c9923adaa
    federal_funds_rate DECIMAL(18,4) NULL,
    -- column_id: 7b69eb2d-16e1-41c9-9c91-40db9ea2ce80
    sp500_index STRING NULL,
    -- column_id: 6a86bd05-29c1-4310-bc97-d92f5785b373
    vix_index STRING NULL,
    -- column_id: b68adaf1-62c1-4261-9d55-4ac88cad14e2
    consumer_confidence_index STRING NULL,
    -- column_id: 1ed09d30-90e9-463b-84c2-47554b22f5be
    housing_price_index DECIMAL(18,4) NULL,
    -- column_id: 9cc4011d-face-4060-8307-bb8eb1c02544
    `10yr_treasury_yield` DECIMAL(18,4) NULL,
    -- column_id: 3fc7facb-5dd8-4713-802c-7bee23fa525e
    mortgage_rate_30yr DECIMAL(18,4) NULL,
    -- column_id: 067c7e23-1107-4dca-85b1-a1936190b909
    created_at DATETIME NULL,
    -- column_id: 70126d34-7eb0-47ff-ba5e-db6606153cf3
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(date)
DISTRIBUTED BY HASH(date) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
