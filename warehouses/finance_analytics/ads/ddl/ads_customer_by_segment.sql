DROP TABLE IF EXISTS finance_analytics_dm.ads_customer_by_segment;
-- table_id: 76af8719-5f2b-4b8c-a090-81547d1a4c47
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_customer_by_segment (
    -- column_id: 1f28bd5d-28c2-47da-a614-96b4e290c443
    customer_segment VARCHAR(255) NULL,
    -- column_id: 16748daa-9f76-4453-9844-de0d4b6e9f7e
    customer_count BIGINT NULL,
    -- column_id: 73ce8237-0de3-4d87-9393-d78e54b8d910
    pct_of_total DECIMAL(18,4) NULL,
    -- column_id: 8f30bffd-7bca-4f53-9bda-b38fd29e2aec
    avg_clv STRING NULL,
    -- column_id: 18c4ea6f-8f6d-49fa-90ef-f8c37c571eb7
    avg_income DECIMAL(18,4) NULL,
    -- column_id: 35785ccf-84a0-4357-a7f2-5c0ceaf9e573
    avg_credit_score DECIMAL(18,4) NULL,
    -- column_id: 1cd27247-b459-466d-864a-a40bc5f386be
    avg_tenure_months STRING NULL,
    -- column_id: 83bb65a2-8465-429e-bea0-752a54cf0a1f
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(customer_segment)
DISTRIBUTED BY HASH(customer_segment) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
