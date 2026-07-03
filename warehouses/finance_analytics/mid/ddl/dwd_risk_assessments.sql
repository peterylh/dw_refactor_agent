DROP TABLE IF EXISTS finance_analytics_dm.dwd_risk_assessments;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_risk_assessments (
    assessment_id BIGINT NULL,
    customer_id BIGINT NULL,
    assessment_date DATETIME NULL,
    assessment_type STRING NULL,
    next_review_date DATETIME NULL,
    risk_rating STRING NULL,
    risk_score DECIMAL(18,4) NULL,
    credit_risk STRING NULL,
    fraud_risk STRING NULL,
    aml_risk STRING NULL,
    kyc_status STRING NULL,
    kyc_last_updated STRING NULL,
    pep_flag BOOLEAN NULL,
    sanctions_flag BOOLEAN NULL,
    adverse_media_flag BOOLEAN NULL,
    high_value_customer DECIMAL(18,4) NULL,
    requires_enhanced_due_diligence STRING NULL,
    transaction_volume_last_90d DECIMAL(18,4) NULL,
    num_accounts BIGINT NULL,
    years_as_customer BIGINT NULL,
    employment_verified STRING NULL,
    income_verified DECIMAL(18,4) NULL,
    address_verified STRING NULL,
    regulatory_concerns STRING NULL,
    assessor_id STRING NULL,
    assessment_notes STRING NULL,
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(assessment_id)
DISTRIBUTED BY HASH(assessment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
