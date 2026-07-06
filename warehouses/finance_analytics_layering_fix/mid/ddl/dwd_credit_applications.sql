DROP TABLE IF EXISTS finance_analytics_dm.dwd_credit_applications;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_credit_applications (
    application_id BIGINT NULL,
    customer_id BIGINT NULL,
    product_id BIGINT NULL,
    application_date DATETIME NULL,
    requested_amount DECIMAL(18,4) NULL,
    requested_term_months STRING NULL,
    credit_score_at_application DECIMAL(18,4) NULL,
    annual_income DECIMAL(18,4) NULL,
    debt_to_income_ratio DECIMAL(18,4) NULL,
    dti_category STRING NULL,
    employment_length_years STRING NULL,
    decision STRING NULL,
    decision_date DATETIME NULL,
    approved_amount DECIMAL(18,4) NULL,
    approved_rate DECIMAL(18,4) NULL,
    application_channel STRING NULL,
    approval_probability_score DECIMAL(18,4) NULL,
    risk_grade STRING NULL,
    processing_days BIGINT NULL,
    is_approved BOOLEAN NULL,
    amount_difference DECIMAL(18,4) NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(application_id)
DISTRIBUTED BY HASH(application_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
