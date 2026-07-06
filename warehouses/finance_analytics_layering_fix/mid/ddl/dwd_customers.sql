DROP TABLE IF EXISTS finance_analytics_dm.dwd_customers;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_customers (
    customer_id BIGINT NULL,
    first_name STRING NULL,
    last_name STRING NULL,
    email STRING NULL,
    phone_clean STRING NULL,
    date_of_birth STRING NULL,
    age BIGINT NULL,
    ssn STRING NULL,
    address STRING NULL,
    city STRING NULL,
    state STRING NULL,
    zip_code STRING NULL,
    country STRING NULL,
    signup_date DATETIME NULL,
    credit_score DECIMAL(18,4) NULL,
    credit_score_band DECIMAL(18,4) NULL,
    annual_income DECIMAL(18,4) NULL,
    income_bracket DECIMAL(18,4) NULL,
    employment_status STRING NULL,
    employer STRING NULL,
    job_title STRING NULL,
    education_level STRING NULL,
    marital_status STRING NULL,
    number_of_dependents BIGINT NULL,
    home_ownership STRING NULL,
    customer_segment STRING NULL,
    life_stage STRING NULL,
    risk_segment STRING NULL,
    loyalty_tier STRING NULL,
    is_active BOOLEAN NULL,
    preferred_channel STRING NULL,
    marketing_opt_in STRING NULL,
    customer_lifetime_value DECIMAL(18,4) NULL,
    churn_risk_score DECIMAL(18,4) NULL,
    churn_risk_category STRING NULL,
    last_login_date DATETIME NULL,
    acquisition_channel STRING NULL,
    tenure_months BIGINT NULL,
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
