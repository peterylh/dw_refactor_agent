DROP TABLE IF EXISTS finance_analytics_dm.dws_customer_segment_history;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_customer_segment_history (
    segment_history_key CHAR(32) NULL,
    customer_key CHAR(32) NULL,
    effective_date_key CHAR(32) NULL,
    end_date_key CHAR(32) NULL,
    segment_history_id BIGINT NULL,
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
    segment_changed_flag BOOLEAN NULL,
    tier_changed_flag BOOLEAN NULL,
    risk_changed_flag BOOLEAN NULL,
    tier_movement STRING NULL,
    premium_eligible_flag BOOLEAN NULL,
    churn_risk_flag BOOLEAN NULL,
    cross_sell_opportunity_flag BOOLEAN NULL,
    days_in_segment STRING NULL,
    segment_change_count BIGINT NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(segment_history_key)
DISTRIBUTED BY HASH(segment_history_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
