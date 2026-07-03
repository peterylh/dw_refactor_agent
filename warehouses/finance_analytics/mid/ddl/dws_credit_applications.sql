DROP TABLE IF EXISTS finance_analytics_dm.dws_credit_applications;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_credit_applications (
    application_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    product_key CHAR(32) NULL,
    application_date_key CHAR(32) NULL,
    decision_date_key CHAR(32) NULL,
    application_id BIGINT NULL,
    application_date DATETIME NULL,
    decision_date DATETIME NULL,
    decision STRING NULL,
    application_channel STRING NULL,
    risk_grade STRING NULL,
    dti_category STRING NULL,
    requested_amount DECIMAL(18,4) NULL,
    requested_term_months STRING NULL,
    credit_score_at_application DECIMAL(18,4) NULL,
    annual_income DECIMAL(18,4) NULL,
    debt_to_income_ratio DECIMAL(18,4) NULL,
    employment_length_years STRING NULL,
    approved_amount DECIMAL(18,4) NULL,
    approved_rate DECIMAL(18,4) NULL,
    approval_probability_score DECIMAL(18,4) NULL,
    processing_days BIGINT NULL,
    amount_difference DECIMAL(18,4) NULL,
    approved_flag BOOLEAN NULL,
    denied_flag BOOLEAN NULL,
    application_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(application_key)
DISTRIBUTED BY HASH(application_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
