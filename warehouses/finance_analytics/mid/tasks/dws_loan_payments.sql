-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dws_loan_payments;

INSERT INTO finance_analytics_dm.dws_loan_payments
WITH payment_facts AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(lp.payment_id AS STRING), '_dbt_null_'))) AS payment_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(lp.account_id AS STRING), '_dbt_null_'))) AS account_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(lp.customer_id AS STRING), '_dbt_null_'))) AS customer_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(lp.scheduled_date AS DATE) AS STRING), '_dbt_null_'))) AS scheduled_date_key,
        MD5(CONCAT_WS('||', COALESCE(CAST(CAST(lp.actual_date AS DATE) AS STRING), '_dbt_null_'))) AS actual_date_key,
        
        lp.payment_id,
        lp.scheduled_date,
        lp.actual_date,
        lp.payment_status,
        lp.payment_method,
        lp.payment_completeness,
        lp.delinquency_bucket,
        
        -- Measures
        lp.scheduled_amount,
        lp.actual_amount,
        lp.amount_difference,
        lp.late_fee,
        lp.outstanding_balance,
        lp.days_late,
        
        -- Flags
        CASE WHEN lp.is_late THEN 1 ELSE 0 END AS late_payment_flag,
        CASE WHEN lp.payment_status = 'Missed' THEN 1 ELSE 0 END AS missed_payment_flag,
        CASE WHEN lp.payment_completeness = 'Full' THEN 1 ELSE 0 END AS full_payment_flag,
        
        -- Counts
        1 AS payment_count,
        
        CURRENT_TIMESTAMP AS dbt_updated_at
        
    FROM finance_analytics_dm.dwd_loan_payments lp
)

SELECT * FROM payment_facts;
