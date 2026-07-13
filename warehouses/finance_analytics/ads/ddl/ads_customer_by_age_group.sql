DROP TABLE IF EXISTS finance_analytics_dm.ads_customer_by_age_group;
-- table_id: bbd77bd5-bcd0-4761-a517-9f290b37ff3e
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ads_customer_by_age_group (
    -- column_id: f34410be-ba84-4302-84c1-5bd458f3587d
    age_group VARCHAR(255) NULL,
    -- column_id: 0f480b5e-4e60-4832-854c-00fd6315114a
    customer_count BIGINT NULL,
    -- column_id: 432d8f4b-87af-419e-bba2-472aadf3a962
    pct_of_total DECIMAL(18,4) NULL,
    -- column_id: b86d0403-b1e4-4ec8-b4ec-fcea92fa3bbe
    avg_clv STRING NULL,
    -- column_id: ac259a73-e8b3-4201-ab94-cfb460f49a05
    avg_income DECIMAL(18,4) NULL,
    -- column_id: 0e0aacce-15de-4e80-8757-7c13b3a1ca57
    active_count BIGINT NULL,
    -- column_id: 838365af-895d-4785-b407-7f21da413321
    last_updated DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(age_group)
DISTRIBUTED BY HASH(age_group) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
