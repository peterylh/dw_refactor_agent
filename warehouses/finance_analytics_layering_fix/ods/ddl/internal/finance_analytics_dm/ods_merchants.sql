DROP TABLE IF EXISTS finance_analytics_dm.ods_merchants;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_merchants (
    merchant_id BIGINT NULL,
    merchant_name STRING NULL,
    category STRING NULL,
    mcc_code STRING NULL,
    city STRING NULL,
    state STRING NULL,
    country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    risk_rating STRING NULL,
    avg_transaction_amount DECIMAL(18,4) NULL,
    is_online BOOLEAN NULL,
    established_date DATETIME NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(merchant_id)
DISTRIBUTED BY HASH(merchant_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
