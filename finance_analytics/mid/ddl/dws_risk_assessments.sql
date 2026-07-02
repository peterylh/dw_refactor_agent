DROP TABLE IF EXISTS finance_analytics_dm.dws_risk_assessments;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_risk_assessments (
    assessment_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    assessment_date_key CHAR(32) NULL,
    next_review_date_key CHAR(32) NULL,
    assessment_id BIGINT NULL,
    assessment_date DATETIME NULL,
    assessment_type STRING NULL,
    next_review_date DATETIME NULL,
    risk_rating STRING NULL,
    credit_risk STRING NULL,
    fraud_risk STRING NULL,
    aml_risk STRING NULL,
    kyc_status STRING NULL,
    kyc_last_updated STRING NULL,
    assessor_id STRING NULL,
    risk_score DECIMAL(18,4) NULL,
    transaction_volume_last_90d DECIMAL(18,4) NULL,
    num_accounts BIGINT NULL,
    years_as_customer BIGINT NULL,
    credit_risk_score DECIMAL(18,4) NULL,
    fraud_risk_score DECIMAL(18,4) NULL,
    aml_risk_score DECIMAL(18,4) NULL,
    days_until_review STRING NULL,
    kyc_age_days STRING NULL,
    pep_flag BOOLEAN NULL,
    sanctions_flag BOOLEAN NULL,
    adverse_media_flag BOOLEAN NULL,
    high_value_flag BOOLEAN NULL,
    edd_required_flag BOOLEAN NULL,
    employment_verified_flag BOOLEAN NULL,
    income_verified_flag BOOLEAN NULL,
    address_verified_flag BOOLEAN NULL,
    kyc_compliant_flag BOOLEAN NULL,
    high_risk_customer_flag BOOLEAN NULL,
    assessment_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(assessment_key)
DISTRIBUTED BY HASH(assessment_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
