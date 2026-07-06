-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_customer_monthly_summary;

INSERT INTO finance_analytics_dm.dws_customer_monthly_summary
WITH monthly_transactions AS (
    SELECT
        customer_id,
        DATE_FORMAT(transaction_date, '%Y-%m') AS year_month,
        COUNT(*) AS transaction_count,
        SUM(amount_abs) AS total_transaction_volume,
        AVG(amount_abs) AS avg_transaction_amount,
        SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS fraud_transaction_count,
        SUM(CASE WHEN is_fraud THEN amount_abs ELSE 0 END) AS fraud_amount,
        COUNT(DISTINCT merchant_id) AS unique_merchants,
        COUNT(DISTINCT merchant_category) AS unique_categories,
        SUM(CASE WHEN is_international THEN 1 ELSE 0 END) AS international_transaction_count
    FROM finance_analytics_dm.dwd_transactions
    
    GROUP BY customer_id, DATE_FORMAT(transaction_date, '%Y-%m')
),

monthly_accounts AS (
    SELECT
        customer_id,
        DATE_FORMAT(CURRENT_DATE, '%Y-%m') AS year_month,
        COUNT(*) AS active_account_count,
        SUM(current_balance) AS total_balance,
        AVG(current_balance) AS avg_balance,
        SUM(CASE WHEN is_past_due THEN 1 ELSE 0 END) AS past_due_account_count
    FROM finance_analytics_dm.dwd_accounts
    WHERE is_active = TRUE
    GROUP BY customer_id
),

monthly_summary AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(t.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        t.year_month,
        
        -- Transaction Metrics
        t.transaction_count,
        t.total_transaction_volume,
        t.avg_transaction_amount,
        t.fraud_transaction_count,
        t.fraud_amount,
        t.unique_merchants,
        t.unique_categories,
        t.international_transaction_count,
        
        -- Account Metrics
        COALESCE(a.active_account_count, 0) AS active_account_count,
        COALESCE(a.total_balance, 0) AS total_balance,
        COALESCE(a.avg_balance, 0) AS avg_balance,
        COALESCE(a.past_due_account_count, 0) AS past_due_account_count,
        
        -- Calculated Metrics
        CASE 
            WHEN t.transaction_count > 0 
            THEN ROUND(CAST(t.fraud_transaction_count AS DECIMAL(18,4)) / t.transaction_count * 100, 2)
            ELSE 0 
        END AS fraud_rate_pct,
        
        1 AS customer_count,
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM monthly_transactions t
    LEFT JOIN monthly_accounts a 
        ON t.customer_id = a.customer_id 
        AND t.year_month = a.year_month
)

SELECT * FROM monthly_summary;
