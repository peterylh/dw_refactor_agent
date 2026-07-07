DROP TABLE IF EXISTS finance_analytics_dm.ods_atm_locations;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_atm_locations (
    atm_id BIGINT NULL,
    atm_code STRING NULL,
    location_name STRING NULL,
    location_type STRING NULL,
    address STRING NULL,
    city STRING NULL,
    state STRING NULL,
    zip_code STRING NULL,
    country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    install_date DATETIME NULL,
    is_operational BOOLEAN NULL,
    is_deposit_enabled BOOLEAN NULL,
    is_cash_only BOOLEAN NULL,
    max_withdrawal_amount DECIMAL(18,4) NULL,
    daily_transaction_limit BIGINT NULL,
    avg_daily_transactions BIGINT NULL,
    cash_capacity STRING NULL,
    last_refill_date DATETIME NULL,
    last_maintenance_date DATETIME NULL,
    surcharge_fee DECIMAL(18,4) NULL,
    is_24_hour BOOLEAN NULL,
    has_camera BOOLEAN NULL,
    branch_id BIGINT NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(atm_id)
DISTRIBUTED BY HASH(atm_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
