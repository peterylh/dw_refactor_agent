DROP TABLE IF EXISTS finance_analytics_dm.dwd_fraud_alerts;
-- table_id: 8e6523b5-2517-4c86-9659-b285879bcbf4
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_fraud_alerts (
    -- column_id: 3437c261-ae40-4c39-bb34-02f312b0ec4c
    alert_id BIGINT NULL,
    -- column_id: 2ac5ef90-637b-43db-b170-c4fd08994863
    transaction_id BIGINT NULL,
    -- column_id: 8d4107a0-c3f1-42b3-baf0-dc47b3e0152a
    customer_id BIGINT NULL,
    -- column_id: 4fff2233-a3d5-4fb6-98ca-e129f0d6c544
    account_id BIGINT NULL,
    -- column_id: 17853a84-d41a-43c2-b8ef-ea9a71d2d1c4
    alert_date DATETIME NULL,
    -- column_id: f5780046-8496-49f8-80aa-b172df18404c
    alert_type STRING NULL,
    -- column_id: 0c612d67-4a01-4a70-921a-b1ecd6da7f71
    alert_severity STRING NULL,
    -- column_id: cbbe21d2-dd78-4cee-a065-8e8427e583b5
    investigation_status STRING NULL,
    -- column_id: 50dda38b-f7a7-48e7-b0b7-b73db805734d
    resolution_date DATETIME NULL,
    -- column_id: 7c8fb4b7-fafd-4c75-9859-74fd76b6c25b
    amount_recovered DECIMAL(18,4) NULL,
    -- column_id: 08c600d2-0ea6-43dd-864c-94c26447291a
    assigned_to STRING NULL,
    -- column_id: f3d97c3e-4ea4-4e38-92e8-d3d65fd1c7cd
    notes STRING NULL,
    -- column_id: 905d2069-fe96-4a14-bcf7-504e27002398
    resolution_days BIGINT NULL,
    -- column_id: 1a1e65e0-6002-4b09-9e3f-4638c86ee9a4
    is_resolved BOOLEAN NULL,
    -- column_id: dae4a790-3d3c-4df7-86c5-d535ef490dbb
    is_confirmed_fraud BOOLEAN NULL,
    -- column_id: 3260089c-4c7c-45a4-9660-5b5a8b09d18b
    is_false_positive BOOLEAN NULL,
    -- column_id: 73ffb5ae-620c-40e2-9e1d-75aafa02a313
    recovered_amount DECIMAL(18,4) NULL,
    -- column_id: bee22519-1ec0-457c-8f8c-8bce8e4ff9c3
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(alert_id)
DISTRIBUTED BY HASH(alert_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
