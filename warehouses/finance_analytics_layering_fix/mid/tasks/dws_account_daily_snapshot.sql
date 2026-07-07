-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_account_daily_snapshot;

INSERT INTO finance_analytics_dm.dws_account_daily_snapshot
WITH daily_snapshots AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(a.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CURRENT_DATE AS STRING), '_dbt_null_'))) AS snapshot_date_key,
        a.customer_id,
        MD5(CONCAT_WS('||', COALESCE(CAST(a.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(a.product_id AS STRING), '_dbt_null_'))) AS product_key,
        
        -- Snapshot Date
        CURRENT_DATE AS snapshot_date,
        
        -- Balance Measures
        a.current_balance,
        a.available_balance,
        a.credit_limit,
        a.credit_utilization_pct,
        
        -- Status Measures
        a.account_age_months,
        CASE WHEN a.is_active THEN 1 ELSE 0 END AS active_account_count,
        CASE WHEN a.is_closed THEN 1 ELSE 0 END AS closed_account_count,
        CASE WHEN a.is_dormant THEN 1 ELSE 0 END AS dormant_account_count,
        CASE WHEN a.is_past_due THEN 1 ELSE 0 END AS past_due_count,
        CASE WHEN a.is_near_limit THEN 1 ELSE 0 END AS near_limit_count,
        
        -- Transaction Activity (from transactions)
        COALESCE(t.daily_transaction_count, 0) AS daily_transaction_count,
        COALESCE(t.daily_transaction_amount, 0) AS daily_transaction_amount,
        COALESCE(t.daily_debit_count, 0) AS daily_debit_count,
        COALESCE(t.daily_credit_count, 0) AS daily_credit_count,
        
        1 AS account_count,
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_accounts a
    LEFT JOIN (
        SELECT
            account_id,
            COUNT(*) AS daily_transaction_count,
            SUM(amount) AS daily_transaction_amount,
            SUM(CASE WHEN amount < 0 THEN 1 ELSE 0 END) AS daily_debit_count,
            SUM(CASE WHEN amount > 0 THEN 1 ELSE 0 END) AS daily_credit_count
        FROM finance_analytics_dm.dwd_transactions
        WHERE CAST(transaction_date AS DATE) = CURRENT_DATE
        GROUP BY account_id
    ) t ON a.account_id = t.account_id
    
    
)

SELECT * FROM daily_snapshots;
