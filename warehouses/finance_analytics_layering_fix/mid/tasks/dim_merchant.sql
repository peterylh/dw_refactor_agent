-- Auto-generated from dbt model
TRUNCATE TABLE finance_analytics_dm.dim_merchant;

INSERT INTO finance_analytics_dm.dim_merchant
WITH merchant_enhanced AS (
    SELECT
        MD5(CONCAT_WS('||', COALESCE(CAST(merchant_id AS STRING), '_dbt_null_'))) AS merchant_key,
        merchant_id AS merchant_natural_key,
        merchant_name,
        category,
        mcc_code,
        category_group,
        city,
        state,
        country,
        latitude,
        longitude,
        region,
        risk_rating,
        risk_score,
        avg_transaction_amount,
        transaction_value_segment,
        is_online,
        merchant_type,
        established_date,
        years_in_business,
        business_maturity,
        mcc_category,
        CURRENT_TIMESTAMP AS dbt_updated_at
    FROM finance_analytics_dm.dwd_merchants
)

SELECT * FROM merchant_enhanced;
