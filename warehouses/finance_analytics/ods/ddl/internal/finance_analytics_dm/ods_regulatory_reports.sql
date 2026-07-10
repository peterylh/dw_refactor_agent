DROP TABLE IF EXISTS finance_analytics_dm.ods_regulatory_reports;
-- table_id: ce3f9a15-54dd-48c2-8536-d60c8e8e55fd
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_regulatory_reports (
    -- column_id: bf4133a5-0d07-4ada-b789-4fa120fb0766
    report_id BIGINT NULL,
    -- column_id: 7c1c0e12-c72b-4cd7-a8d9-2af09a345bfe
    report_type_code STRING NULL,
    -- column_id: 528d05f2-1722-4f29-b61b-856a71898909
    report_type_name STRING NULL,
    -- column_id: dd3f0ab5-db05-4c26-a369-8d59e6eda960
    report_period_start STRING NULL,
    -- column_id: bc7c0127-5aab-4fc7-be7c-e640ce15ac09
    report_period_end STRING NULL,
    -- column_id: 3955e602-6728-4765-9ec3-70ba6158bdfb
    filing_date DATETIME NULL,
    -- column_id: 055a609e-51ea-4b48-9b01-29230b1d44ba
    due_date DATETIME NULL,
    -- column_id: 94764d5b-5bde-4e2d-9b6e-0901aaf3baaf
    actual_filing_date DATETIME NULL,
    -- column_id: bc0adba6-89bc-4891-8c8f-1648047c2a2b
    filing_status STRING NULL,
    -- column_id: a334eac2-2b0d-4413-a0c1-3b5ebd57e714
    report_frequency STRING NULL,
    -- column_id: ce8bde73-071b-4070-aa67-4ba2c7b8f791
    regulator STRING NULL,
    -- column_id: 793b8125-75cf-402f-b0ff-fd73db013802
    customer_id BIGINT NULL,
    -- column_id: 19c9b041-39ac-413e-8e0d-f4b5971a360d
    account_id BIGINT NULL,
    -- column_id: c6df321d-fdd7-408a-a07a-2f58b9cb9348
    transaction_id BIGINT NULL,
    -- column_id: beca1610-6ea6-4fa7-b85a-30c2ff000c06
    amount_reported DECIMAL(18,4) NULL,
    -- column_id: 4e6fb615-2125-49b9-9cc6-7954105b8d03
    risk_level STRING NULL,
    -- column_id: 37848ac9-8f5d-41ab-8655-702930f43aef
    requires_follow_up STRING NULL,
    -- column_id: 53b7ac9b-634a-4de7-aacf-93b4a3ba86ca
    follow_up_date DATETIME NULL,
    -- column_id: 9f8b43e9-2180-45f5-839d-ab47693b4983
    assigned_to STRING NULL,
    -- column_id: 0e9c78e6-467a-44f8-bdae-a2dc7a362999
    reviewed_by STRING NULL,
    -- column_id: f36a4d3c-7cd7-466b-a2c1-3732bcca45a8
    approval_date DATETIME NULL,
    -- column_id: 7b643714-0207-4e24-8ede-9b6c99fad1df
    filing_method STRING NULL,
    -- column_id: 9a28698d-7ca8-473e-92e4-e0d175048eed
    confirmation_number STRING NULL,
    -- column_id: 9eed2740-f4a6-4a7e-a058-0634557a40d8
    findings STRING NULL,
    -- column_id: c8666cb6-302c-45bc-9074-f5647dcccb05
    internal_notes STRING NULL,
    -- column_id: 6792dd5d-27ec-4a16-ac88-820c9f8a484f
    is_amended BOOLEAN NULL,
    -- column_id: 8b9206f8-fa07-4c07-9221-c7d7443230e2
    original_report_id STRING NULL,
    -- column_id: b16f049c-305c-408b-96fd-49fdb552a802
    penalty_amount DECIMAL(18,4) NULL,
    -- column_id: 0d322741-5d6c-4e2c-a912-6d122b6148ec
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(report_id)
DISTRIBUTED BY HASH(report_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
