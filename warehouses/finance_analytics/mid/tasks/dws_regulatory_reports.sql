-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_regulatory_reports;

INSERT INTO finance_analytics_dm.dws_regulatory_reports
WITH regulatory_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(rr.report_id AS STRING), '_dbt_null_'))) AS report_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(rr.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(rr.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(rr.transaction_id AS STRING), '_dbt_null_'))) AS transaction_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(rr.filing_date AS DATE) AS STRING), '_dbt_null_'))) AS filing_date_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(rr.due_date AS DATE) AS STRING), '_dbt_null_'))) AS due_date_key,
        
        rr.report_id,
        rr.report_type_code,
        rr.report_type_name,
        rr.report_frequency,
        rr.regulator,
        rr.report_period_start,
        rr.report_period_end,
        rr.filing_date,
        rr.due_date,
        rr.actual_filing_date,
        rr.filing_status,
        rr.filing_method,
        rr.confirmation_number,
        rr.risk_level,
        rr.assigned_to,
        rr.reviewed_by,
        rr.approval_date,
        
        -- Measures
        rr.amount_reported,
        rr.penalty_amount,
        
        -- Timeliness Metrics
        CASE 
            WHEN rr.actual_filing_date IS NOT NULL AND rr.due_date IS NOT NULL
            THEN DATEDIFF(rr.actual_filing_date, rr.due_date)
            ELSE NULL
        END AS days_from_due_date,
        
        CASE
            WHEN rr.actual_filing_date IS NOT NULL AND rr.filing_date IS NOT NULL
            THEN DATEDIFF(rr.actual_filing_date, rr.filing_date)
            ELSE NULL
        END AS processing_days,
        
        -- Flags
        CASE WHEN rr.filing_status = 'Filed' THEN 1 ELSE 0 END AS filed_flag,
        CASE WHEN rr.filing_status = 'Pending' THEN 1 ELSE 0 END AS pending_flag,
        CASE WHEN rr.filing_status = 'Late' THEN 1 ELSE 0 END AS late_flag,
        CASE WHEN rr.requires_follow_up THEN 1 ELSE 0 END AS requires_follow_up_flag,
        CASE WHEN rr.is_amended THEN 1 ELSE 0 END AS amended_flag,
        CASE WHEN rr.penalty_amount > 0 THEN 1 ELSE 0 END AS penalty_assessed_flag,
        CASE 
            WHEN rr.actual_filing_date IS NOT NULL 
                AND rr.due_date IS NOT NULL 
                AND CAST(rr.actual_filing_date AS DATE) > CAST(rr.due_date AS DATE) 
            THEN 1 
            ELSE 0 
        END AS filed_late_flag,
        
        -- Risk Classification
        CASE
            WHEN rr.risk_level = 'High' THEN 3
            WHEN rr.risk_level = 'Medium' THEN 2
            WHEN rr.risk_level = 'Low' THEN 1
            ELSE 0
        END AS risk_score,
        
        -- Counts
        1 AS report_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_regulatory_reports rr
)

SELECT * FROM regulatory_facts;
