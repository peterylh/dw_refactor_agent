DROP TABLE IF EXISTS finance_analytics_dm.dws_fraud_alerts;
-- table_id: 49ca8901-76b3-457d-8b7b-52dbce707dbb
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_fraud_alerts (
    -- column_id: 9f1e9108-f6eb-49d7-b1cc-3b12f3de5391
    alert_key CHAR(32) NULL,
    -- column_id: 2c88249e-5d19-49da-9048-5bcbfb727174
    transaction_key CHAR(32) NULL,
    -- column_id: fce9f990-d974-4a96-9714-0b7a10cd64f7
    customer_key CHAR(32) NULL,
    -- column_id: 1a2c7a57-d99d-430a-ad72-e17da2d860ef
    account_key CHAR(32) NULL,
    -- column_id: 7457d768-e89b-4089-b80e-6e15697654dc
    alert_date_key CHAR(32) NULL,
    -- column_id: db4204e1-0ac4-46bd-a9ff-aed9b717e264
    resolution_date_key CHAR(32) NULL,
    -- column_id: ec71d1fc-90b2-42c4-a0c3-182aec0c049a
    alert_id BIGINT NULL,
    -- column_id: 84c066a5-7fc5-4f06-9577-e3a2236f5f26
    alert_date DATETIME NULL,
    -- column_id: 6b2c872e-3229-46f9-809b-0a02e2ed3b0d
    alert_type STRING NULL,
    -- column_id: 3fda4c62-2c30-4ca7-820a-50b551e4cc6e
    alert_severity STRING NULL,
    -- column_id: 3739a5ff-8829-4764-b9f0-c2bcbaf1b1db
    investigation_status STRING NULL,
    -- column_id: aabb72e2-534d-45fd-a08c-be6cf12cb580
    resolution_date DATETIME NULL,
    -- column_id: 9dad8a1e-aa60-4f04-a7c4-b2b0e62153f9
    assigned_to STRING NULL,
    -- column_id: a738b91b-a966-464b-ad25-609ec7c99711
    amount_recovered DECIMAL(18,4) NULL,
    -- column_id: 0b71d43e-09cb-4b75-a760-b6d861a4cfeb
    resolution_days BIGINT NULL,
    -- column_id: 6c6b5016-08a3-475c-a50f-4e30d247ed86
    resolved_flag BOOLEAN NULL,
    -- column_id: a5e827c6-9b54-4be5-8ee6-d347c4e60b20
    confirmed_fraud_flag BOOLEAN NULL,
    -- column_id: b32a8012-3048-4176-bf48-8ffee318d010
    false_positive_flag BOOLEAN NULL,
    -- column_id: a5ff6db4-2fd4-4554-8759-14747d5a2f9a
    alert_count BIGINT NULL,
    -- column_id: 38721570-dee9-47bc-9f48-ff71cb9ac63d
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(alert_key)
DISTRIBUTED BY HASH(alert_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
