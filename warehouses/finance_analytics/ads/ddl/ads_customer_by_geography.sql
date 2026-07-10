DROP TABLE IF EXISTS finance_analytics_dm.ads_customer_by_geography;
-- table_id: 13fb4fdb-912d-4b7d-bba2-21e3134f76df
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_customer_by_geography (
    -- column_id: c632ac4e-c6e5-4fd9-8c36-83c137174cfe
    state VARCHAR(255) NULL,
    -- column_id: 6ff88508-7ef1-4ce2-9567-29fbd590d767
    city STRING NULL,
    -- column_id: ad2cbfce-7fce-4a1d-b6b5-4630b03cea79
    customer_count BIGINT NULL,
    -- column_id: 762a7032-b2f8-4bee-92e1-a4f888540241
    pct_of_total DECIMAL(18,4) NULL,
    -- column_id: 0f7c0b88-55f2-4e84-93e8-63b3a4f55c24
    avg_clv STRING NULL,
    -- column_id: 1b9e6a29-f41a-4352-8498-d8c1f9f66123
    avg_income DECIMAL(18,4) NULL,
    -- column_id: c19a1ca4-900c-4ec7-a39a-25f385707133
    active_count BIGINT NULL,
    -- column_id: 19d9cf4d-d70f-4685-9c12-5ea92f2b30be
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(state)
DISTRIBUTED BY HASH(state) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
