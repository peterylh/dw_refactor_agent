-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_customers;

INSERT INTO finance_analytics_dm.dwd_customers
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_customers
),

cleaned AS (
    SELECT
        -- Primary Key
        customer_id,
        
        -- Personal Information (cleaned)
        TRIM(UPPER(first_name)) AS first_name,
        TRIM(UPPER(last_name)) AS last_name,
        TRIM(LOWER(email)) AS email,
        REGEXP_REPLACE(phone, '[^0-9]', '', 'g') AS phone_clean,
        date_of_birth,
        age,
        ssn,
        
        -- Address (standardized)
        TRIM(address) AS address,
        TRIM(UPPER(city)) AS city,
        TRIM(UPPER(state)) AS state,
        zip_code,
        TRIM(UPPER(country)) AS country,
        
        -- Account Information
        signup_date,
        CASE 
            WHEN credit_score < 300 THEN 300
            WHEN credit_score > 850 THEN 850
            ELSE credit_score
        END AS credit_score,
        
        -- Credit Score Bands
        CASE
            WHEN credit_score >= 800 THEN 'Excellent'
            WHEN credit_score >= 740 THEN 'Very Good'
            WHEN credit_score >= 670 THEN 'Good'
            WHEN credit_score >= 580 THEN 'Fair'
            ELSE 'Poor'
        END AS credit_score_band,
        
        annual_income,
        
        -- Income Brackets
        CASE
            WHEN annual_income < 30000 THEN 'Low'
            WHEN annual_income < 75000 THEN 'Medium'
            WHEN annual_income < 150000 THEN 'High'
            ELSE 'Very High'
        END AS income_bracket,
        
        employment_status,
        employer,
        job_title,
        education_level,
        marital_status,
        number_of_dependents,
        home_ownership,
        
        -- Segmentation
        customer_segment,
        life_stage,
        risk_segment,
        loyalty_tier,
        
        -- Status
        is_active,
        preferred_channel,
        marketing_opt_in,
        
        -- Metrics
        customer_lifetime_value,
        churn_risk_score,
        
        -- Churn Risk Category
        CASE
            WHEN churn_risk_score >= 0.6 THEN 'High Risk'
            WHEN churn_risk_score >= 0.4 THEN 'Medium Risk'
            ELSE 'Low Risk'
        END AS churn_risk_category,
        
        last_login_date,
        acquisition_channel,
        
        -- Tenure Calculation
        TIMESTAMPDIFF(MONTH, signup_date, CURRENT_DATE) AS tenure_months,
        
        -- Metadata
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE customer_id IS NOT NULL
      AND email IS NOT NULL
)

SELECT * FROM cleaned;
