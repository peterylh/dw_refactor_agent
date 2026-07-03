-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_customer;

INSERT INTO finance_analytics_dm.dim_customer
WITH customer_current AS (
    SELECT 
        customer_id,
        first_name,
        last_name,
        email,
        phone_clean,
        date_of_birth,
        age,
        address,
        city,
        state,
        zip_code,
        country,
        signup_date,
        credit_score,
        credit_score_band,
        annual_income,
        income_bracket,
        employment_status,
        employer,
        job_title,
        education_level,
        marital_status,
        number_of_dependents,
        home_ownership,
        customer_segment,
        life_stage,
        risk_segment,
        loyalty_tier,
        is_active,
        preferred_channel,
        marketing_opt_in,
        customer_lifetime_value,
        churn_risk_score,
        churn_risk_category,
        last_login_date,
        acquisition_channel,
        tenure_months
    FROM finance_analytics_dm.dwd_customers
),

customer_with_surrogate AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        customer_id AS customer_natural_key,
        first_name,
        last_name,
        first_name || ' ' || last_name AS full_name,
        email,
        phone_clean,
        date_of_birth,
        age,
        CASE 
            WHEN age < 25 THEN '18-24'
            WHEN age < 35 THEN '25-34'
            WHEN age < 45 THEN '35-44'
            WHEN age < 55 THEN '45-54'
            WHEN age < 65 THEN '55-64'
            ELSE '65+'
        END AS age_group,
        address,
        city,
        state,
        zip_code,
        country,
        signup_date,
        credit_score,
        credit_score_band,
        annual_income,
        income_bracket,
        employment_status,
        employer,
        job_title,
        education_level,
        marital_status,
        number_of_dependents,
        home_ownership,
        customer_segment,
        life_stage,
        risk_segment,
        loyalty_tier,
        is_active,
        preferred_channel,
        marketing_opt_in,
        customer_lifetime_value,
        churn_risk_score,
        churn_risk_category,
        last_login_date,
        acquisition_channel,
        tenure_months,
        CURRENT_TIMESTAMP AS effective_date,
        CAST('9999-12-31' AS DATETIME) AS expiration_date,
        TRUE AS is_current,
        CURRENT_TIMESTAMP AS dbt_updated_at
    FROM customer_current
)

SELECT * FROM customer_with_surrogate;
