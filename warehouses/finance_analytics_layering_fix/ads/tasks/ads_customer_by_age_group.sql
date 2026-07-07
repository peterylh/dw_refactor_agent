-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.ads_customer_by_age_group;

INSERT INTO finance_analytics_dm.ads_customer_by_age_group
SELECT
    age_group,
    COUNT(DISTINCT customer_key) AS customer_count,
    ROUND(COUNT(DISTINCT customer_key) * 100.0 / SUM(COUNT(DISTINCT customer_key)) OVER (), 2) AS pct_of_total,
    ROUND(AVG(customer_lifetime_value), 2) AS avg_clv,
    ROUND(AVG(annual_income), 2) AS avg_income,
    COUNT(DISTINCT CASE WHEN is_active THEN customer_key END) AS active_count,
    CURRENT_TIMESTAMP AS last_updated
FROM finance_analytics_dm.dim_customer
WHERE is_current = TRUE
GROUP BY age_group
ORDER BY age_group;
