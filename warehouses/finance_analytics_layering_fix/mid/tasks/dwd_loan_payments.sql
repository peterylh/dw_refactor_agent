-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dwd_loan_payments;

INSERT INTO finance_analytics_dm.dwd_loan_payments
WITH source AS (
    SELECT * FROM finance_analytics_dm.ods_loan_payments
),

cleaned AS (
    SELECT
        payment_id,
        account_id,
        customer_id,
        scheduled_date,
        actual_date,
        scheduled_amount,
        actual_amount,
        is_late,
        days_late,
        late_fee,
        payment_method,
        outstanding_balance,
        
        -- Payment Status
        CASE
            WHEN actual_date IS NULL AND scheduled_date < CURRENT_DATE THEN 'Missed'
            WHEN is_late THEN 'Late'
            WHEN actual_date IS NOT NULL THEN 'Paid'
            ELSE 'Scheduled'
        END AS payment_status,
        
        -- Payment Completeness
        CASE
            WHEN actual_amount >= scheduled_amount THEN 'Full'
            WHEN actual_amount > 0 THEN 'Partial'
            ELSE 'None'
        END AS payment_completeness,
        
        -- Amount Difference
        actual_amount - scheduled_amount AS amount_difference,
        
        -- Delinquency Category
        CASE
            WHEN days_late = 0 THEN 'Current'
            WHEN days_late <= 30 THEN '1-30 Days'
            WHEN days_late <= 60 THEN '31-60 Days'
            WHEN days_late <= 90 THEN '61-90 Days'
            ELSE '90+ Days'
        END AS delinquency_bucket,
        
        CURRENT_TIMESTAMP AS updated_at
        
    FROM source
    WHERE payment_id IS NOT NULL
)

SELECT * FROM cleaned;
