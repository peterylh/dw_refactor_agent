DROP TABLE IF EXISTS finance_analytics_dm.dwd_credit_applications;
-- table_id: 9870d8be-ea62-4cf8-9914-0a94976bcaf3
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_credit_applications (
    -- column_id: ac203162-f0d3-406a-97e1-9afa34395997
    application_id BIGINT NULL,
    -- column_id: 032fb34b-02d7-48c4-8ae7-f58fd7b23e19
    customer_id BIGINT NULL,
    -- column_id: c2a88b00-f56d-4a03-8664-510f63b11465
    product_id BIGINT NULL,
    -- column_id: 32d52ba8-2028-4479-aa0f-03c3f3f3abf7
    application_date DATETIME NULL,
    -- column_id: c0931ad4-ddd0-4d03-aa11-2704b88176db
    requested_amount DECIMAL(18,4) NULL,
    -- column_id: 6b589111-7f01-4286-b54f-52ed3680339d
    requested_term_months STRING NULL,
    -- column_id: 550c42d3-a26c-4e2f-b003-dc084adc3788
    credit_score_at_application DECIMAL(18,4) NULL,
    -- column_id: 10053afb-0638-44a4-a803-7d62d1bd0595
    annual_income DECIMAL(18,4) NULL,
    -- column_id: cd74ceaf-46ea-4288-9a6c-2f0d227750c2
    debt_to_income_ratio DECIMAL(18,4) NULL,
    -- column_id: 815945f0-ab2e-4206-915b-f08ae0ef8223
    dti_category STRING NULL,
    -- column_id: 4bcd232a-07d2-4c87-9493-f934213d97e9
    employment_length_years STRING NULL,
    -- column_id: 030104e6-988b-49bb-95df-278cf019a245
    decision STRING NULL,
    -- column_id: a8e36d0f-a6bb-41f3-8d7e-30c215d2d100
    decision_date DATETIME NULL,
    -- column_id: 768a4b0d-6254-40fd-ae19-7a9a991981e3
    approved_amount DECIMAL(18,4) NULL,
    -- column_id: 50964252-dd00-4de2-9d05-0bf0ee4b0a47
    approved_rate DECIMAL(18,4) NULL,
    -- column_id: d456f27b-247d-4c62-ad6b-dd0f66797790
    application_channel STRING NULL,
    -- column_id: d1bcc76e-2ae5-4cd6-af5a-a3e89fe84054
    approval_probability_score DECIMAL(18,4) NULL,
    -- column_id: ada39138-f875-407b-bff3-e5b21a4913e3
    risk_grade STRING NULL,
    -- column_id: 09c1f947-aff9-4ed0-849f-a3b8520a7a8d
    processing_days BIGINT NULL,
    -- column_id: f30283ea-2361-43a9-b82f-7040c4534ba5
    is_approved BOOLEAN NULL,
    -- column_id: 78660930-a394-4bca-9dbb-177acb6c9ea4
    amount_difference DECIMAL(18,4) NULL,
    -- column_id: 39df9192-7bf9-49f3-aa1f-7f647358ccfa
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(application_id)
DISTRIBUTED BY HASH(application_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
