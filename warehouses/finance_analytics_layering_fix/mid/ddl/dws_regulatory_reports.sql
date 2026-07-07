DROP TABLE IF EXISTS finance_analytics_dm.dws_regulatory_reports;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_regulatory_reports (
    report_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    account_key CHAR(32) NULL,
    transaction_key CHAR(32) NULL,
    filing_date_key CHAR(32) NULL,
    due_date_key CHAR(32) NULL,
    report_id BIGINT NULL,
    report_type_code STRING NULL,
    report_type_name STRING NULL,
    report_frequency STRING NULL,
    regulator STRING NULL,
    report_period_start STRING NULL,
    report_period_end STRING NULL,
    filing_date DATETIME NULL,
    due_date DATETIME NULL,
    actual_filing_date DATETIME NULL,
    filing_status STRING NULL,
    filing_method STRING NULL,
    confirmation_number STRING NULL,
    risk_level STRING NULL,
    assigned_to STRING NULL,
    reviewed_by STRING NULL,
    approval_date DATETIME NULL,
    amount_reported DECIMAL(18,4) NULL,
    penalty_amount DECIMAL(18,4) NULL,
    days_from_due_date DATETIME NULL,
    processing_days BIGINT NULL,
    filed_flag BOOLEAN NULL,
    pending_flag BOOLEAN NULL,
    late_flag BOOLEAN NULL,
    requires_follow_up_flag BOOLEAN NULL,
    amended_flag BOOLEAN NULL,
    penalty_assessed_flag BOOLEAN NULL,
    filed_late_flag BOOLEAN NULL,
    risk_score DECIMAL(18,4) NULL,
    report_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(report_key)
DISTRIBUTED BY HASH(report_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
