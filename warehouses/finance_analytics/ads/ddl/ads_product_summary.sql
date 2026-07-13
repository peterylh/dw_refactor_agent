DROP TABLE IF EXISTS finance_analytics_dm.ads_product_summary;
-- table_id: 2db593d1-e10d-4858-969a-7929cbe44a8d
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_product_summary (
    -- column_id: 9cad0b40-b1e5-4a30-a34f-2ef1d3d90a87
    total_products VARCHAR(255) NULL,
    -- column_id: acf6800c-7596-490a-8a31-26691b2a7d28
    premium_products STRING NULL,
    -- column_id: 88c7c651-6c87-49b6-9fe2-185b442ad5bd
    deposit_products STRING NULL,
    -- column_id: dee5ffb2-7098-4d7d-b345-d7bac727be44
    credit_products STRING NULL,
    -- column_id: 27bf6cd5-07ce-4eac-9a5b-b07a64c1fd9c
    loan_products STRING NULL,
    -- column_id: 826f9017-cd25-4471-990b-5df223f5f77e
    investment_products STRING NULL,
    -- column_id: 8753bd6d-a5ad-4dea-8e6c-8dca21ec9f5a
    avg_interest_rate_pct DECIMAL(18,4) NULL,
    -- column_id: 734d40b3-da35-4314-811d-7328055eacc0
    avg_monthly_fee DECIMAL(18,4) NULL,
    -- column_id: b7e1b139-50eb-4981-9d41-0966afd1a994
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(total_products)
DISTRIBUTED BY HASH(total_products) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
