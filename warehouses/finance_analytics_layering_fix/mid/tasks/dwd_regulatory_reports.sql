-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_regulatory_reports;

INSERT INTO finance_analytics_dm.dwd_regulatory_reports
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_regulatory_reports
),

cleaned AS (
    SELECT
        -- Primary Key
        report_id,
        
        -- Report Identification
        UPPER(TRIM(report_type_code)) AS report_type_code,
        TRIM(report_type_name) AS report_type_name,
        report_frequency,
        TRIM(regulator) AS regulator,
        
        -- Reporting Period
        report_period_start,
        report_period_end,
        
        -- Filing Dates
        filing_date,
        due_date,
        actual_filing_date,
        filing_status,
        filing_method,
        TRIM(confirmation_number) AS confirmation_number,
        
        -- Related Entities
        customer_id,
        account_id,
        transaction_id,
        
        -- Report Details
        CAST(amount_reported AS DECIMAL(15,2)) AS amount_reported,
        risk_level,
        TRIM(findings) AS findings,
        
        -- Follow-up
        requires_follow_up,
        follow_up_date,
        
        -- Staff
        TRIM(assigned_to) AS assigned_to,
        TRIM(reviewed_by) AS reviewed_by,
        approval_date,
        
        -- Amendment Info
        is_amended,
        original_report_id,
        
        -- Penalties
        CAST(penalty_amount AS DECIMAL(12,2)) AS penalty_amount,
        
        -- Notes
        TRIM(internal_notes) AS internal_notes,
        
        -- Metadata
        CURRENT_TIMESTAMP AS created_at
        
    FROM source
    WHERE report_id IS NOT NULL
)

SELECT * FROM cleaned;
