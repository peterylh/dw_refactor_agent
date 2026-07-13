DROP TABLE IF EXISTS finance_analytics_dm.dwd_regulatory_reports;
-- table_id: a41c281f-3863-40ce-9723-950944fc89f0
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_regulatory_reports (
    -- column_id: d5ff1570-7d03-4143-8604-a420350178d8
    report_id BIGINT NULL,
    -- column_id: af472df9-93e3-49fd-99d2-45e51438eabd
    report_type_code STRING NULL,
    -- column_id: ef36a640-6122-4cdc-b603-44047e461b7b
    report_type_name STRING NULL,
    -- column_id: ce954f07-0ac0-4f84-87fd-b2810747a457
    report_frequency STRING NULL,
    -- column_id: 8dc59d37-16ed-49ae-b035-54c11296fb9b
    regulator STRING NULL,
    -- column_id: dcc01911-90ca-4000-beda-90eaeb2ae686
    report_period_start STRING NULL,
    -- column_id: 71a3b110-1e3a-4a89-8ecd-eacaddda32e9
    report_period_end STRING NULL,
    -- column_id: e26979f3-6442-427c-ba85-3f1ca260d666
    filing_date DATETIME NULL,
    -- column_id: ea1447db-69f0-4149-a58a-abc8cedbf94b
    due_date DATETIME NULL,
    -- column_id: 97acde21-e9be-40ad-b8a0-e4bbb6251bcb
    actual_filing_date DATETIME NULL,
    -- column_id: 0a691bda-1112-464f-bb44-93aa3814f862
    filing_status STRING NULL,
    -- column_id: e1332ded-9186-4edc-bf24-59e3f1a75047
    filing_method STRING NULL,
    -- column_id: f93ee9af-f699-4b5c-b2c1-98615821735c
    confirmation_number STRING NULL,
    -- column_id: 33aea4f1-6828-4acd-8291-7ee01753cda1
    customer_id BIGINT NULL,
    -- column_id: fa08c763-ffd5-43b5-ba04-9ed889a01528
    account_id BIGINT NULL,
    -- column_id: 79c7f463-bed5-4213-a6e2-f0c67041a774
    transaction_id BIGINT NULL,
    -- column_id: 819cd2ec-3e77-41fc-9725-ac0ccd0fae11
    amount_reported DECIMAL(18,4) NULL,
    -- column_id: 4f0d9bc9-1807-415d-a467-63059e09d9b6
    risk_level STRING NULL,
    -- column_id: 0acdd1e9-1c26-4966-9f88-2c45d9c9498e
    findings STRING NULL,
    -- column_id: d667d981-977e-4de2-bf03-7d90b8140c5d
    requires_follow_up STRING NULL,
    -- column_id: c2e4309c-1bb0-44df-bacc-76012e285d28
    follow_up_date DATETIME NULL,
    -- column_id: 75016d83-5094-49cd-a5ed-9801bdb8aac6
    assigned_to STRING NULL,
    -- column_id: ff15d298-577d-46ad-a568-42c728afeb73
    reviewed_by STRING NULL,
    -- column_id: 1f395912-6ead-43c7-b76d-228911abf703
    approval_date DATETIME NULL,
    -- column_id: 0351300d-d8ef-4db7-8227-f360288da069
    is_amended BOOLEAN NULL,
    -- column_id: 7d29d3f3-6077-49d8-ab32-fc285c9cea7b
    original_report_id STRING NULL,
    -- column_id: 880fabcd-42b9-4689-a1e7-7d764e1c6f2b
    penalty_amount DECIMAL(18,4) NULL,
    -- column_id: e1f01f2e-e4d4-460e-92dd-3500ed8f576d
    internal_notes STRING NULL,
    -- column_id: fc90e196-50d4-4bdb-b7fe-e4120a288fee
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(report_id)
DISTRIBUTED BY HASH(report_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
