DROP TABLE IF EXISTS finance_analytics_dm.dws_credit_applications;
-- table_id: 7eb6dd45-f9f6-45fc-bb75-84ff60268f39
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_credit_applications (
    -- column_id: 10b9dacd-6992-451f-a801-a3cee6475411
    application_key CHAR(32) NULL,
    -- column_id: 4bb6b2e9-481b-4eed-9c52-727888550e9e
    customer_key CHAR(32) NULL,
    -- column_id: 7df89a45-8c01-4bff-a3f7-bbddc4dff13f
    product_key CHAR(32) NULL,
    -- column_id: 90db5481-1095-4a4d-8d6f-78eee45d196c
    application_date_key CHAR(32) NULL,
    -- column_id: 4f245e2d-336e-4833-87a6-41db73ce919b
    decision_date_key CHAR(32) NULL,
    -- column_id: 9c7c87d2-a0a2-48a5-8d9b-5da06bc4c3ed
    application_id BIGINT NULL,
    -- column_id: fcff8019-f454-46b4-946a-87b2314c0c06
    application_date DATETIME NULL,
    -- column_id: f0a61327-cda0-40c4-adbf-6ac475d4c4b7
    decision_date DATETIME NULL,
    -- column_id: 4604076d-3b21-41f8-bed9-6d0e2e99692f
    decision STRING NULL,
    -- column_id: a0325660-de3c-43e1-92c2-d2bd2dc6aa87
    application_channel STRING NULL,
    -- column_id: 7a98f280-a239-43b2-b0fe-091eca65f2b6
    risk_grade STRING NULL,
    -- column_id: aa38f6b3-5cd8-4766-8de3-1bbec237027a
    dti_category STRING NULL,
    -- column_id: 27c6f7a8-3457-4b25-8241-b810dd25658e
    requested_amount DECIMAL(18,4) NULL,
    -- column_id: 9fb6e05d-8502-4b5c-898a-4e2c91b2079c
    requested_term_months STRING NULL,
    -- column_id: db5dab9c-aa97-4763-b745-a888dc4844db
    credit_score_at_application DECIMAL(18,4) NULL,
    -- column_id: 9ff3943b-ff0b-4995-8d40-194bccd2e07b
    annual_income DECIMAL(18,4) NULL,
    -- column_id: 8fa71f0d-5e76-4072-b747-903919917ef3
    debt_to_income_ratio DECIMAL(18,4) NULL,
    -- column_id: 8e220ccd-dcde-4ec1-98c6-a76a06cc94c2
    employment_length_years STRING NULL,
    -- column_id: 2bfdfbe4-bc3c-4a4d-b05a-9c3249ae163e
    approved_amount DECIMAL(18,4) NULL,
    -- column_id: 89924f5a-5b75-49fb-ab0d-4cd41978b666
    approved_rate DECIMAL(18,4) NULL,
    -- column_id: bcd27637-5cf1-4b61-b748-34190fcc7097
    approval_probability_score DECIMAL(18,4) NULL,
    -- column_id: a0df9f67-a140-4f6c-ba43-2d3890349cf9
    processing_days BIGINT NULL,
    -- column_id: 710a1750-878d-44f2-83f4-bcfbb2eb8477
    amount_difference DECIMAL(18,4) NULL,
    -- column_id: e2abce2c-e7e4-4697-b2d6-4577b14fc421
    approved_flag BOOLEAN NULL,
    -- column_id: 2c1213a1-a972-4bae-b397-83d3bb984a66
    denied_flag BOOLEAN NULL,
    -- column_id: bdea41f5-ca26-4d8b-b257-abc9b4bca344
    application_count BIGINT NULL,
    -- column_id: 2490aaf8-49d6-49b8-9504-125fe5f28b1f
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(application_key)
DISTRIBUTED BY HASH(application_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
