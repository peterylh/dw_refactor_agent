DROP TABLE IF EXISTS finance_analytics_dm.dim_location;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_location (
    location_key CHAR(32) NULL,
    location_natural_key BIGINT NULL,
    location_type STRING NULL,
    location_name STRING NULL,
    location_code STRING NULL,
    address STRING NULL,
    city STRING NULL,
    state STRING NULL,
    zip_code STRING NULL,
    country STRING NULL,
    latitude DECIMAL(18,4) NULL,
    longitude DECIMAL(18,4) NULL,
    region STRING NULL,
    phone STRING NULL,
    is_active BOOLEAN NULL,
    is_operational BOOLEAN NULL,
    is_24_hour BOOLEAN NULL,
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(location_key)
DISTRIBUTED BY HASH(location_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
