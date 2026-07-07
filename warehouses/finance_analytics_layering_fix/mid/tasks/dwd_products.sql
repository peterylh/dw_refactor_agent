-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_products;

INSERT INTO finance_analytics_dm.dwd_products
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_products
),

cleaned AS (
    SELECT
        -- Primary Key
        product_id,
        
        -- Product Information (cleaned)
        TRIM(product_name) AS product_name,
        TRIM(UPPER(category)) AS category,
        
        -- Product Hierarchy
        CASE
            WHEN category IN ('Deposit') THEN 'Banking'
            WHEN category IN ('Credit', 'Loan') THEN 'Lending'
            WHEN category IN ('Investment') THEN 'Wealth Management'
            ELSE 'Other'
        END AS product_line,
        
        -- Financial Terms
        interest_rate,
        ROUND(CAST((interest_rate * 100) AS DECIMAL(18,4)), 2) AS interest_rate_pct,
        min_balance,
        monthly_fee,
        overdraft_limit,
        
        -- Product Tier & Premium Flag
        product_tier,
        is_premium,
        
        -- Product Type Description
        CASE
            WHEN is_premium THEN 'Premium Product'
            ELSE 'Standard Product'
        END AS product_type_desc,
        
        -- Fee Structure Classification
        CASE
            WHEN monthly_fee = 0 THEN 'No Fee'
            WHEN monthly_fee < 10 THEN 'Low Fee'
            WHEN monthly_fee < 50 THEN 'Medium Fee'
            ELSE 'High Fee'
        END AS fee_category,
        
        -- Interest Rate Bands
        CASE
            WHEN interest_rate = 0 THEN 'No Interest'
            WHEN interest_rate <= 0.05 THEN 'Low Rate'
            WHEN interest_rate <= 0.10 THEN 'Medium Rate'
            ELSE 'High Rate'
        END AS rate_category,
        
        -- Product Complexity Score (0-100)
        CASE
            WHEN category = 'Deposit' AND monthly_fee = 0 THEN 10
            WHEN category = 'Deposit' THEN 20
            WHEN category = 'Credit' AND NOT is_premium THEN 40
            WHEN category = 'Credit' AND is_premium THEN 60
            WHEN category = 'Loan' THEN 70
            WHEN category = 'Investment' THEN 90
            ELSE 50
        END AS complexity_score,
        
        -- Target Customer Segment
        CASE
            WHEN product_tier = 'Basic' THEN 'Mass Market'
            WHEN product_tier = 'Standard' THEN 'Mass Market,Affluent'
            WHEN product_tier = 'Premium' THEN 'Affluent,Premium'
            WHEN product_tier = 'Business' THEN 'Business'
            ELSE 'All Segments'
        END AS target_segment,
        
        -- Risk Level
        CASE
            WHEN category = 'Deposit' THEN 'Low Risk'
            WHEN category = 'Credit' AND interest_rate > 0.15 THEN 'High Risk'
            WHEN category = 'Credit' THEN 'Medium Risk'
            WHEN category = 'Loan' THEN 'Medium Risk'
            WHEN category = 'Investment' THEN 'Variable Risk'
            ELSE 'Unknown'
        END AS risk_level,
        
        -- Profitability Indicator (simplified)
        CASE
            WHEN monthly_fee > 0 THEN 'Fee-Based Revenue'
            WHEN interest_rate > 0.10 THEN 'Interest-Based Revenue'
            WHEN category = 'Deposit' THEN 'Deposits for Lending'
            ELSE 'Relationship Product'
        END AS revenue_model,
        
        -- Metadata
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE product_id IS NOT NULL
      AND product_name IS NOT NULL
)

SELECT * FROM cleaned;
