DROP TABLE IF EXISTS finance_analytics_dm.ods_branch_locations;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_branch_locations (
    branch_id BIGINT NULL,
    branch_name STRING NULL,
    branch_code STRING NULL,
    branch_type STRING NULL,
    address STRING NULL,
    city STRING NULL,
    state STRING NULL,
    zip_code STRING NULL,
    country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    phone STRING NULL,
    open_date DATETIME NULL,
    is_active BOOLEAN NULL,
    square_footage STRING NULL,
    num_employees BIGINT NULL,
    avg_daily_customers STRING NULL,
    has_safe_deposit BOOLEAN NULL,
    has_notary BOOLEAN NULL,
    has_coin_counter BOOLEAN NULL,
    wheelchair_accessible STRING NULL,
    operating_hours STRING NULL,
    manager_name STRING NULL,
    region STRING NULL,
    created_at DATETIME NULL,
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(branch_id)
DISTRIBUTED BY HASH(branch_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
