-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.ads_customer_by_segment;

INSERT INTO finance_analytics_dm.ads_customer_by_segment
SELECT
    customer_segment,
    COUNT(DISTINCT customer_key) AS customer_count,
    ROUND(COUNT(DISTINCT customer_key) * 100.0 / SUM(COUNT(DISTINCT customer_key)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(customer_lifetime_value), 2) AS avg_clv,
    ROUND(AVG(annual_income), 2) AS avg_income,
    ROUND(AVG(credit_score), 0) AS avg_credit_score,
    ROUND(AVG(tenure_months), 1) AS avg_tenure_months,
    CURRENT_TIMESTAMP AS last_updated
FROM finance_analytics_dm.dim_customer
WHERE is_current = TRUE
GROUP BY customer_segment
ORDER BY customer_count DESC;
