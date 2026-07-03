-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_credit_applications;

INSERT INTO finance_analytics_dm.dwd_credit_applications
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_credit_applications
),

cleaned AS (
    SELECT
        application_id,
        customer_id,
        product_id,
        CAST(application_date AS DATETIME) AS application_date,
        
        -- Application Details
        requested_amount,
        requested_term_months,
        credit_score_at_application,
        annual_income,
        debt_to_income_ratio,
        employment_length_years,
        
        -- DTI Categories
        CASE
            WHEN debt_to_income_ratio < 0.20 THEN 'Excellent'
            WHEN debt_to_income_ratio < 0.36 THEN 'Good'
            WHEN debt_to_income_ratio < 0.43 THEN 'Fair'
            ELSE 'Poor'
        END AS dti_category,
        
        -- Decision
        decision,
        CAST(decision_date AS DATETIME) AS decision_date,
        approved_amount,
        approved_rate,
        application_channel,
        
        -- Scores
        approval_probability_score,
        risk_grade,
        
        -- Processing Time
        DAY((CAST(decision_date AS DATETIME) - CAST(application_date AS DATETIME))) AS processing_days,
        
        -- Approval Flag
        CASE WHEN decision = 'Approved' THEN TRUE ELSE FALSE END AS is_approved,
        
        -- Amount Difference
        CASE 
            WHEN approved_amount IS NOT NULL 
            THEN approved_amount - requested_amount 
            ELSE NULL 
        END AS amount_difference,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE application_id IS NOT NULL
)

SELECT * FROM cleaned;
