-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_risk_assessments;

INSERT INTO finance_analytics_dm.dwd_risk_assessments
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_risk_assessments
),

cleaned AS (
    SELECT
        -- Primary Keys
        assessment_id,
        customer_id,
        
        -- Assessment Details
        assessment_date,
        assessment_type,
        next_review_date,
        
        -- Risk Ratings
        risk_rating,
        ROUND(CAST(risk_score AS DECIMAL(5,3)), 3) AS risk_score,
        credit_risk,
        fraud_risk,
        aml_risk,
        
        -- KYC Status
        kyc_status,
        kyc_last_updated,
        
        -- Risk Flags
        pep_flag,
        sanctions_flag,
        adverse_media_flag,
        high_value_customer,
        requires_enhanced_due_diligence,
        
        -- Customer Context
        ROUND(CAST(transaction_volume_last_90d AS DECIMAL(15,2)), 2) AS transaction_volume_last_90d,
        num_accounts,
        ROUND(CAST(years_as_customer AS DECIMAL(6,2)), 2) AS years_as_customer,
        
        -- Verification Status
        employment_verified,
        income_verified,
        address_verified,
        
        -- Regulatory
        TRIM(regulatory_concerns) AS regulatory_concerns,
        
        -- Assessment Metadata
        TRIM(assessor_id) AS assessor_id,
        TRIM(assessment_notes) AS assessment_notes,
        
        -- Metadata
        
        CURRENT_TIMESTAMP AS created_at
        
    FROM source
    WHERE assessment_id IS NOT NULL
      AND customer_id IS NOT NULL
)

SELECT * FROM cleaned;
