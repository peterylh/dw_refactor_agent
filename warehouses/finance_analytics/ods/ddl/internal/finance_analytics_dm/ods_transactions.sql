DROP TABLE IF EXISTS finance_analytics_dm.ods_transactions;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_transactions (
    transaction_id BIGINT NULL,
    account_id BIGINT NULL,
    customer_id BIGINT NULL,
    merchant_id BIGINT NULL,
    transaction_date DATETIME NULL,
    transaction_type STRING NULL,
    amount DECIMAL(18,4) NULL,
    currency STRING NULL,
    channel STRING NULL,
    merchant_category STRING NULL,
    mcc_code STRING NULL,
    description STRING NULL,
    is_fraud BOOLEAN NULL,
    fraud_score DECIMAL(18,4) NULL,
    location_city STRING NULL,
    location_state STRING NULL,
    location_country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    device_id STRING NULL,
    ip_address STRING NULL,
    is_international BOOLEAN NULL,
    authorization_code STRING NULL,
    card_last_four STRING NULL,
    is_recurring BOOLEAN NULL,
    hour_of_day BIGINT NULL,
    day_of_week BIGINT NULL,
    is_weekend BOOLEAN NULL,
    distance_from_home_km STRING NULL,
    merchant_risk_score DECIMAL(18,4) NULL,
    velocity_24h BIGINT NULL,
    amount_deviation_score DECIMAL(18,4) NULL,
    processing_time_ms STRING NULL,
    decline_reason STRING NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(transaction_id)
DISTRIBUTED BY HASH(transaction_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
