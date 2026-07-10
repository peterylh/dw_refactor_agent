DROP TABLE IF EXISTS finance_analytics_dm.ods_credit_applications;
-- table_id: 6d1a8c92-14d8-4ef5-9f38-9ee549ab24aa
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_credit_applications (
    -- column_id: 0c508086-5028-42db-936a-7b4947991260
    application_id BIGINT NULL,
    -- column_id: e63dfe06-effa-451e-995c-498a08ecbab8
    customer_id BIGINT NULL,
    -- column_id: 327e0025-d10f-4b14-bf4e-4bafa63ab407
    product_id BIGINT NULL,
    -- column_id: 9e295ff5-cc77-40fd-a181-7df913c36fca
    application_date DATETIME NULL,
    -- column_id: 5fe3b2c8-f472-49f9-91b6-edf02a89a342
    requested_amount DECIMAL(18,4) NULL,
    -- column_id: 10c54904-d63d-4702-a110-ccb44e0226b4
    requested_term_months STRING NULL,
    -- column_id: 017d954d-905c-47c0-949c-a4cde846a731
    credit_score_at_application DECIMAL(18,4) NULL,
    -- column_id: 1de9ee9b-f168-4590-8c21-1748c8667a32
    annual_income DECIMAL(18,4) NULL,
    -- column_id: 2c94e294-089a-4276-ad97-a20d163e53e2
    debt_to_income_ratio DECIMAL(18,4) NULL,
    -- column_id: 11be5695-6e42-46e9-9f42-ef686046ca95
    employment_length_years STRING NULL,
    -- column_id: fca7c0ef-cad1-41f3-a8ee-a3a499ee7ff9
    decision STRING NULL,
    -- column_id: d3f4b8c6-3f16-49f4-8b2a-6c4527cc7c4f
    decision_date DATETIME NULL,
    -- column_id: e8395d58-3b1d-4c78-9ecd-dfc0db993a37
    approved_amount DECIMAL(18,4) NULL,
    -- column_id: 516051a6-025a-4246-ae94-6393943936f9
    approved_rate DECIMAL(18,4) NULL,
    -- column_id: 7843c5f6-8556-4120-8610-3628717f9487
    application_channel STRING NULL,
    -- column_id: 2f03e0d3-978a-4b25-88ed-4eac6f825c47
    approval_probability_score DECIMAL(18,4) NULL,
    -- column_id: e09a6eb1-40aa-4f97-8349-897e9957e8d4
    risk_grade STRING NULL,
    -- column_id: b748b326-5589-48f9-b5be-0fd606a17cb7
    created_at DATETIME NULL,
    -- column_id: c1bc2862-7d7a-42ca-a2ee-48ebd9ef584c
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(application_id)
DISTRIBUTED BY HASH(application_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
