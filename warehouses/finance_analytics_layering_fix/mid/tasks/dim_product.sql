-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_product;

INSERT INTO finance_analytics_dm.dim_product
WITH product_enhanced AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(product_id AS STRING), '_dbt_null_'))) AS product_key,
        product_id AS product_natural_key,
        product_name,
        category,
        product_line,
        interest_rate,
        interest_rate_pct,
        min_balance,
        monthly_fee,
        overdraft_limit,
        product_tier,
        is_premium,
        product_type_desc,
        fee_category,
        rate_category,
        complexity_score,
        target_segment,
        risk_level,
        revenue_model,
        CURRENT_TIMESTAMP AS dbt_updated_at
    FROM finance_analytics_dm.dwd_products
)

SELECT * FROM product_enhanced;
