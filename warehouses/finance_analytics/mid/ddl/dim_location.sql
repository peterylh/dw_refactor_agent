DROP TABLE IF EXISTS finance_analytics_dm.dim_location;
-- table_id: ae89040a-3933-48de-ac99-544b911bfdf8
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_location (
    -- column_id: b279ea0c-760c-42a1-9981-67f9edd54ce6
    location_key CHAR(32) NULL,
    -- column_id: f212372e-adc3-4faa-8a69-9b4d58ef4c21
    location_natural_key BIGINT NULL,
    -- column_id: 24c8c65c-02fb-42aa-9929-93bc81f51bfb
    location_type STRING NULL,
    -- column_id: 7f8d632d-f8be-420e-b7c1-3444eb3b6b4f
    location_name STRING NULL,
    -- column_id: 742340b4-67dd-4ca1-a5fd-d43a7490bc29
    location_code STRING NULL,
    -- column_id: 8fe662a4-fdb9-4b00-8e3b-10a7ce0f63d1
    address STRING NULL,
    -- column_id: 3b2886d0-085d-4023-9061-6f6883acf861
    city STRING NULL,
    -- column_id: 5727ff2a-c54d-4eb0-8e15-2880b5c61a4a
    state STRING NULL,
    -- column_id: e267a999-ce43-414f-bf43-622716c85e86
    zip_code STRING NULL,
    -- column_id: 377374d3-2127-4d4f-b695-92a797303da5
    country STRING NULL,
    -- column_id: 8d328308-93e1-456f-b3ab-eed6d52921f8
    latitude DECIMAL(18,4) NULL,
    -- column_id: 99836696-e0ec-42f3-86ec-3bfb16f808a2
    longitude DECIMAL(18,4) NULL,
    -- column_id: e2777157-667f-40fb-9114-41a472acb8e1
    region STRING NULL,
    -- column_id: afe8439a-79f9-482c-a68d-89664c11b29b
    phone STRING NULL,
    -- column_id: 8049d8fc-27c4-402a-92d7-2221ec84d59c
    is_active BOOLEAN NULL,
    -- column_id: 6b08ec2b-76fc-4b5c-9837-f57aca15068a
    is_operational BOOLEAN NULL,
    -- column_id: c096b5b3-14f2-46cb-8479-adde48542e61
    is_24_hour BOOLEAN NULL,
    -- column_id: 3cc8e3c3-2da5-4894-91a5-1d0d861bb143
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(location_key)
DISTRIBUTED BY HASH(location_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
