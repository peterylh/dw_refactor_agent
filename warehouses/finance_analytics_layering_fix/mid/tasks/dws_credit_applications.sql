-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_credit_applications;

INSERT INTO finance_analytics_dm.dws_credit_applications
WITH application_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(ca.application_id AS STRING), '_dbt_null_'))) AS application_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ca.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(ca.product_id AS STRING), '_dbt_null_'))) AS product_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(ca.application_date AS DATE) AS STRING), '_dbt_null_'))) AS application_date_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(ca.decision_date AS DATE) AS STRING), '_dbt_null_'))) AS decision_date_key,
        
        ca.application_id,
        ca.application_date,
        ca.decision_date,
        ca.decision,
        ca.application_channel,
        ca.risk_grade,
        ca.dti_category,
        
        -- Measures
        ca.requested_amount,
        ca.requested_term_months,
        ca.credit_score_at_application,
        ca.annual_income,
        ca.debt_to_income_ratio,
        ca.employment_length_years,
        ca.approved_amount,
        ca.approved_rate,
        ca.approval_probability_score,
        ca.processing_days,
        ca.amount_difference,
        
        -- Flags
        CASE WHEN ca.is_approved THEN 1 ELSE 0 END AS approved_flag,
        CASE WHEN ca.decision = 'Denied' THEN 1 ELSE 0 END AS denied_flag,
        
        -- Counts
        1 AS application_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_credit_applications ca
)

SELECT * FROM application_facts;
