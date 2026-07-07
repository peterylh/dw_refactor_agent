DROP TABLE IF EXISTS finance_analytics_dm.dim_date;
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_date (
    date_key CHAR(32) NULL,
    date_actual DATETIME NULL,
    year BIGINT NULL,
    quarter BIGINT NULL,
    month BIGINT NULL,
    week_of_year BIGINT NULL,
    day_of_year BIGINT NULL,
    day_of_week BIGINT NULL,
    day_name STRING NULL,
    month_name STRING NULL,
    year_month STRING NULL,
    year_quarter STRING NULL,
    is_weekend BOOLEAN NULL,
    is_sunday BOOLEAN NULL,
    is_saturday BOOLEAN NULL,
    first_day_of_month STRING NULL,
    last_day_of_month STRING NULL,
    first_day_of_quarter STRING NULL,
    last_day_of_quarter STRING NULL,
    first_day_of_year STRING NULL,
    last_day_of_year STRING NULL,
    is_first_day_of_month BOOLEAN NULL,
    is_last_day_of_month BOOLEAN NULL
) ENGINE=OLAP
DUPLICATE KEY(date_key)
DISTRIBUTED BY HASH(date_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
