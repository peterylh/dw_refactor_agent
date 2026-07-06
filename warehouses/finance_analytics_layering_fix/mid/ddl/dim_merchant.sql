DROP TABLE IF EXISTS finance_analytics_dm.dim_merchant;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_merchant (
    merchant_key CHAR(32) NULL,
    merchant_natural_key BIGINT NULL,
    merchant_name STRING NULL,
    category STRING NULL,
    mcc_code STRING NULL,
    category_group STRING NULL,
    city STRING NULL,
    state STRING NULL,
    country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    region STRING NULL,
    risk_rating STRING NULL,
    risk_score DECIMAL(18,4) NULL,
    avg_transaction_amount DECIMAL(18,4) NULL,
    transaction_value_segment STRING NULL,
    is_online BOOLEAN NULL,
    merchant_type STRING NULL,
    established_date DATETIME NULL,
    years_in_business STRING NULL,
    business_maturity STRING NULL,
    mcc_category STRING NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(merchant_key)
DISTRIBUTED BY HASH(merchant_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
