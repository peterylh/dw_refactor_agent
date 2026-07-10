DROP TABLE IF EXISTS finance_analytics_dm.dwd_risk_assessments;
-- table_id: 537e4059-111c-420d-a66f-e14ddf2e78a0
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_risk_assessments (
    -- column_id: 9d56d0ab-6cae-443e-b1a1-6c40d330ff5f
    assessment_id BIGINT NULL,
    -- column_id: ab2d7262-e487-44b1-8679-a7ed67c9e8d6
    customer_id BIGINT NULL,
    -- column_id: a334782e-283f-476d-aa70-2854cf01beae
    assessment_date DATETIME NULL,
    -- column_id: 1d9e8dff-ba52-46c6-ab24-9ea45d3d2a32
    assessment_type STRING NULL,
    -- column_id: 38177724-0739-4c76-831f-8033ba9370fd
    next_review_date DATETIME NULL,
    -- column_id: b6c3f48a-7d4a-4eec-9def-b66513d88b2d
    risk_rating STRING NULL,
    -- column_id: c6b0c564-da9d-4fa1-8526-2abeacc68dba
    risk_score DECIMAL(18,4) NULL,
    -- column_id: 914b6076-c3fc-4403-aab8-8131ae20844d
    credit_risk STRING NULL,
    -- column_id: 6e7b56a9-7327-46c1-b18b-27ac07f73f87
    fraud_risk STRING NULL,
    -- column_id: 90c3f6e9-179f-407d-b01a-e18ef3213187
    aml_risk STRING NULL,
    -- column_id: 804d6409-3e67-4919-915a-1c0806620b8a
    kyc_status STRING NULL,
    -- column_id: b8a7a973-b4dc-45e0-ab15-54f34f156f12
    kyc_last_updated STRING NULL,
    -- column_id: 08ebc6a2-ebcc-485c-b097-fd3b11ee55e0
    pep_flag BOOLEAN NULL,
    -- column_id: 14c8dbf0-1911-4dbd-97dc-e22e62717c42
    sanctions_flag BOOLEAN NULL,
    -- column_id: 28892ea5-0cb8-463c-b040-a23b8ed85389
    adverse_media_flag BOOLEAN NULL,
    -- column_id: 839c4f42-84b6-4e8f-8113-98690f94dd64
    high_value_customer DECIMAL(18,4) NULL,
    -- column_id: 3640b7a1-1236-4edd-88d2-5aa418307330
    requires_enhanced_due_diligence STRING NULL,
    -- column_id: eb952423-b4a1-4b48-8eb5-e6b4d36023c5
    transaction_volume_last_90d DECIMAL(18,4) NULL,
    -- column_id: 44a521bb-abb1-4b8a-b8ea-780876bed0f9
    num_accounts BIGINT NULL,
    -- column_id: 3ad1b7e8-c026-4403-a8f1-23c62be7984b
    years_as_customer BIGINT NULL,
    -- column_id: 2bb733e0-84b1-408d-8d20-f2066c2388a7
    employment_verified STRING NULL,
    -- column_id: 73dcec69-ce0d-4d57-b0e9-6c2e00543d24
    income_verified DECIMAL(18,4) NULL,
    -- column_id: 49930670-3492-41bd-9ed6-737910e1e854
    address_verified STRING NULL,
    -- column_id: 200e53de-7717-4d50-be98-4eedfe610688
    regulatory_concerns STRING NULL,
    -- column_id: 328f1ba4-a35e-4441-bffe-a73a00dedc63
    assessor_id STRING NULL,
    -- column_id: 8df3397c-de81-49bd-87b6-8c4a23750977
    assessment_notes STRING NULL,
    -- column_id: 0037bc30-7bcc-4f65-9845-6a2cf8179563
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(assessment_id)
DISTRIBUTED BY HASH(assessment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
