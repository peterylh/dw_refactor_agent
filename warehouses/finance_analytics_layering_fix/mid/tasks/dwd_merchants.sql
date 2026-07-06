-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_merchants;

INSERT INTO finance_analytics_dm.dwd_merchants
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_merchants
),

cleaned AS (
    SELECT
        -- Primary Key
        merchant_id,
        
        -- Merchant Information (cleaned)
        TRIM(merchant_name) AS merchant_name,
        TRIM(UPPER(category)) AS category,
        mcc_code,
        
        -- Category Grouping
        CASE
            WHEN UPPER(category) IN ('GROCERY', 'RESTAURANT', 'GAS STATION') THEN 'Essential Services'
            WHEN UPPER(category) IN ('RETAIL', 'ONLINE SHOPPING') THEN 'Retail'
            WHEN UPPER(category) IN ('ENTERTAINMENT', 'TRAVEL') THEN 'Lifestyle'
            WHEN UPPER(category) IN ('HEALTHCARE', 'EDUCATION') THEN 'Professional Services'
            WHEN UPPER(category) IN ('UTILITIES', 'INSURANCE') THEN 'Utilities & Services'
            ELSE 'Other'
        END AS category_group,
        
        -- Location (standardized)
        TRIM(UPPER(city)) AS city,
        TRIM(UPPER(state)) AS state,
        TRIM(UPPER(country)) AS country,
        
        -- Geographic Coordinates
        latitude,
        longitude,
        
        -- Geographic Region
        CASE
            WHEN state IN ('CA', 'OR', 'WA', 'NV', 'AZ') THEN 'West'
            WHEN state IN ('TX', 'OK', 'NM', 'AR', 'LA') THEN 'South Central'
            WHEN state IN ('FL', 'GA', 'SC', 'NC', 'VA', 'WV', 'KY', 'TN', 'AL', 'MS') THEN 'Southeast'
            WHEN state IN ('IL', 'IN', 'OH', 'MI', 'WI', 'MN', 'IA', 'MO') THEN 'Midwest'
            WHEN state IN ('NY', 'PA', 'NJ', 'CT', 'MA', 'RI', 'VT', 'NH', 'ME') THEN 'Northeast'
            WHEN state IN ('MT', 'ID', 'WY', 'ND', 'SD', 'NE', 'KS') THEN 'Great Plains'
            ELSE 'Other'
        END AS region,
        
        -- Risk Profile
        risk_rating,
        CASE
            WHEN risk_rating = 'High' THEN 3
            WHEN risk_rating = 'Medium' THEN 2
            WHEN risk_rating = 'Low' THEN 1
            ELSE 0
        END AS risk_score,
        
        avg_transaction_amount,
        
        -- Transaction Value Segmentation
        CASE
            WHEN avg_transaction_amount < 50 THEN 'Low Value'
            WHEN avg_transaction_amount < 200 THEN 'Medium Value'
            WHEN avg_transaction_amount < 500 THEN 'High Value'
            ELSE 'Very High Value'
        END AS transaction_value_segment,
        
        -- Merchant Type
        is_online,
        CASE
            WHEN is_online THEN 'Online Merchant'
            ELSE 'Physical Merchant'
        END AS merchant_type,
        
        -- Business Age
        established_date,
        TIMESTAMPDIFF(YEAR, established_date, CURRENT_DATE) AS years_in_business,
        
        -- Business Maturity Classification
        CASE
            WHEN TIMESTAMPDIFF(YEAR, established_date, CURRENT_DATE) < 2 THEN 'New'
            WHEN TIMESTAMPDIFF(YEAR, established_date, CURRENT_DATE) < 5 THEN 'Growing'
            WHEN TIMESTAMPDIFF(YEAR, established_date, CURRENT_DATE) < 10 THEN 'Established'
            ELSE 'Mature'
        END AS business_maturity,
        
        -- MCC Code Category (Major Category)
        CASE
            WHEN mcc_code BETWEEN 1000 AND 1499 THEN 'Agricultural Services'
            WHEN mcc_code BETWEEN 1500 AND 2999 THEN 'Contracted Services'
            WHEN mcc_code BETWEEN 4000 AND 4799 THEN 'Transportation'
            WHEN mcc_code BETWEEN 4800 AND 4999 THEN 'Utilities'
            WHEN mcc_code BETWEEN 5000 AND 5599 THEN 'Retail Outlets'
            WHEN mcc_code BETWEEN 5600 AND 5699 THEN 'Clothing Stores'
            WHEN mcc_code BETWEEN 5700 AND 7299 THEN 'Miscellaneous Stores'
            WHEN mcc_code BETWEEN 7300 AND 7999 THEN 'Business Services'
            WHEN mcc_code BETWEEN 8000 AND 8999 THEN 'Professional Services'
            ELSE 'Other'
        END AS mcc_category,
        
        -- Metadata
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE merchant_id IS NOT NULL
      AND merchant_name IS NOT NULL
)

SELECT * FROM cleaned;
