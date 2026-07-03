DROP TABLE IF EXISTS finance_analytics_dm.dwd_customer_segments_history;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_customer_segments_history (
    segment_history_id BIGINT NULL,
    customer_id BIGINT NULL,
    effective_date DATETIME NULL,
    end_date DATETIME NULL,
    is_current BOOLEAN NULL,
    customer_segment STRING NULL,
    previous_segment STRING NULL,
    loyalty_tier STRING NULL,
    previous_tier STRING NULL,
    risk_segment STRING NULL,
    previous_risk STRING NULL,
    change_type STRING NULL,
    change_reason STRING NULL,
    triggered_by STRING NULL,
    total_accounts BIGINT NULL,
    total_balance DECIMAL(18,4) NULL,
    avg_monthly_transactions STRING NULL,
    products_held BIGINT NULL,
    customer_lifetime_value DECIMAL(18,4) NULL,
    tenure_days BIGINT NULL,
    credit_score DECIMAL(18,4) NULL,
    annual_income DECIMAL(18,4) NULL,
    last_interaction_days STRING NULL,
    digital_engagement_score DECIMAL(18,4) NULL,
    branch_visits_last_90d BIGINT NULL,
    online_logins_last_90d BIGINT NULL,
    eligible_for_premium STRING NULL,
    churn_risk STRING NULL,
    cross_sell_opportunity STRING NULL,
    notes STRING NULL,
    updated_by STRING NULL,
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(segment_history_id)
DISTRIBUTED BY HASH(segment_history_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
