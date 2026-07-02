-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_accounts;

INSERT INTO finance_analytics_dm.dwd_accounts
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_accounts
),

cleaned AS (
    SELECT
        -- Primary Keys
        account_id,
        customer_id,
        product_id,
        
        -- Account Details
        account_number,
        account_status,
        open_date,
        close_date,
        
        -- Account Age
        TIMESTAMPDIFF(MONTH, open_date, COALESCE(close_date, CURRENT_DATE)) AS account_age_months,
        
        -- Status Flags
        CASE WHEN account_status = 'Active' THEN TRUE ELSE FALSE END AS is_active,
        CASE WHEN close_date IS NOT NULL THEN TRUE ELSE FALSE END AS is_closed,
        CASE WHEN account_status = 'Dormant' THEN TRUE ELSE FALSE END AS is_dormant,
        
        -- Balances
        current_balance,
        available_balance,
        credit_limit,
        
        -- Credit Utilization (for credit accounts)
        CASE
            WHEN credit_limit > 0 AND credit_limit IS NOT NULL THEN
                ROUND(ABS(current_balance) / credit_limit * 100, 2)
            ELSE NULL
        END AS credit_utilization_pct,
        
        -- Balance Categories
        CASE
            WHEN current_balance < 0 THEN 'Negative'
            WHEN current_balance = 0 THEN 'Zero'
            WHEN current_balance < 1000 THEN 'Low'
            WHEN current_balance < 10000 THEN 'Medium'
            WHEN current_balance < 100000 THEN 'High'
            ELSE 'Very High'
        END AS balance_category,
        
        currency,
        interest_rate,
        minimum_payment,
        payment_due_date,
        last_statement_date,
        
        -- Account Features
        autopay_enabled,
        overdraft_protection,
        primary_account,
        
        -- Health Indicators
        CASE
            WHEN payment_due_date < CURRENT_DATE AND minimum_payment > 0 THEN TRUE
            ELSE FALSE
        END AS is_past_due,
        
        CASE
            WHEN credit_limit > 0 AND (ABS(current_balance) / credit_limit) > 0.9 THEN TRUE
            ELSE FALSE
        END AS is_near_limit,
        
        -- Metadata
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE account_id IS NOT NULL
)

SELECT * FROM cleaned;
