DROP TABLE IF EXISTS finance_analytics_dm.ods_risk_assessments;
-- table_id: de6bf94e-9499-4ea8-a3fb-8c15486cc691
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_risk_assessments (
    -- column_id: 9ee36677-b0f0-48f7-ac65-c82a84139054
    assessment_id BIGINT NULL,
    -- column_id: 12272b10-8c9a-42fc-89fe-84841120380e
    customer_id BIGINT NULL,
    -- column_id: 4fe16332-49d3-46bb-aa23-6c4a91d41e4a
    assessment_date DATETIME NULL,
    -- column_id: 535622f6-1dce-4ccb-822e-a320a055c089
    assessment_type STRING NULL,
    -- column_id: 96655281-ff23-4638-8bb6-d0d254694505
    risk_rating STRING NULL,
    -- column_id: 6aa0572f-50ba-49cb-992b-0d7d3e9068fd
    risk_score DECIMAL(18,4) NULL,
    -- column_id: da2dd69c-5648-4c02-b2d3-6890da679819
    credit_risk STRING NULL,
    -- column_id: 78184178-8b15-4dd4-823b-97ddade4ec67
    fraud_risk STRING NULL,
    -- column_id: 8c89b46e-cd76-478e-bc32-f3c1a87c63d9
    aml_risk STRING NULL,
    -- column_id: cb22a23d-5eb4-45a4-b8d0-0f10c2c2504c
    kyc_status STRING NULL,
    -- column_id: 4e126f06-b81f-427e-b362-ace6ccafec0e
    kyc_last_updated STRING NULL,
    -- column_id: cebbb63c-ccdf-42c1-8312-845bc58f38e6
    pep_flag BOOLEAN NULL,
    -- column_id: 7d1d5051-a17d-49be-99e7-3236829c7cdc
    sanctions_flag BOOLEAN NULL,
    -- column_id: aa3f3378-2483-4ed0-9cc0-29e35f580ca1
    adverse_media_flag BOOLEAN NULL,
    -- column_id: 59024009-70d4-4170-a98a-0a2fb8bec8f0
    high_value_customer DECIMAL(18,4) NULL,
    -- column_id: 4562dc6d-9cb1-432e-8b81-347be70dde87
    transaction_volume_last_90d DECIMAL(18,4) NULL,
    -- column_id: ddca6e23-26f9-4b62-b5a6-275df83404db
    num_accounts BIGINT NULL,
    -- column_id: 6dafa307-3542-4b7f-a4bf-a18e29ed374c
    years_as_customer BIGINT NULL,
    -- column_id: 4b079902-1dc2-406f-8643-d829ac560703
    employment_verified STRING NULL,
    -- column_id: 08f10f97-d916-4df5-bc87-5269de055bd6
    income_verified DECIMAL(18,4) NULL,
    -- column_id: 379753fd-60af-4c59-aecc-990430dc4341
    address_verified STRING NULL,
    -- column_id: 0504f752-40c7-400a-a596-19a91dacc402
    regulatory_concerns STRING NULL,
    -- column_id: c1991b95-7dc4-40e3-a069-823ae45f291e
    next_review_date DATETIME NULL,
    -- column_id: cdf95edd-ef4c-42c9-b209-0e1650fad765
    assessor_id STRING NULL,
    -- column_id: a0697a24-67b1-4bb2-bc76-e4c1abe254bd
    assessment_notes STRING NULL,
    -- column_id: c9d5e5c0-6f1c-4f38-beaa-b2a20c01c7a5
    requires_enhanced_due_diligence STRING NULL,
    -- column_id: ff376483-690a-4c64-b029-6a4372c9b7ee
    created_at DATETIME NULL,
    -- column_id: a897a2b3-0923-4a90-9d6a-33adcfe3f44e
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(assessment_id)
DISTRIBUTED BY HASH(assessment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
