DROP TABLE IF EXISTS finance_analytics_dm.ods_regulatory_reports;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_regulatory_reports (
    report_id BIGINT NULL,
    report_type_code STRING NULL,
    report_type_name STRING NULL,
    report_period_start STRING NULL,
    report_period_end STRING NULL,
    filing_date DATETIME NULL,
    due_date DATETIME NULL,
    actual_filing_date DATETIME NULL,
    filing_status STRING NULL,
    report_frequency STRING NULL,
    regulator STRING NULL,
    customer_id BIGINT NULL,
    account_id BIGINT NULL,
    transaction_id BIGINT NULL,
    amount_reported DECIMAL(18,4) NULL,
    risk_level STRING NULL,
    requires_follow_up STRING NULL,
    follow_up_date DATETIME NULL,
    assigned_to STRING NULL,
    reviewed_by STRING NULL,
    approval_date DATETIME NULL,
    filing_method STRING NULL,
    confirmation_number STRING NULL,
    findings STRING NULL,
    internal_notes STRING NULL,
    is_amended BOOLEAN NULL,
    original_report_id STRING NULL,
    penalty_amount DECIMAL(18,4) NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(report_id)
DISTRIBUTED BY HASH(report_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
