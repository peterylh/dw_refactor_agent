DROP TABLE IF EXISTS finance_analytics_dm.dwd_atm_locations;
-- table_id: 2ebccea4-b9b4-4b48-b8de-e632cd646c6e
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_atm_locations (
    -- column_id: de9dd4bc-5ce1-48e4-b2b7-1541f2ddcae7
    atm_id BIGINT NULL,
    -- column_id: 032be9f4-939e-4fe9-baab-7cea36314136
    atm_code STRING NULL,
    -- column_id: cb07cb7d-e8da-4213-9de1-64b2c6f00d57
    location_name STRING NULL,
    -- column_id: a13047ff-a22a-4ce3-b2e8-5178c6a20bac
    location_type STRING NULL,
    -- column_id: 60dfb3dc-04e4-4ce2-ae79-a74632e72516
    address STRING NULL,
    -- column_id: 40c7d30f-e253-4021-af6a-5d7259f5b083
    city STRING NULL,
    -- column_id: f146980a-64da-44d4-8301-246534e0397e
    state STRING NULL,
    -- column_id: df07b6f3-1356-409d-961b-4fd8364a9aad
    zip_code STRING NULL,
    -- column_id: a501191e-fb59-404f-b1e5-395480a77be0
    country STRING NULL,
    -- column_id: d3d6cf22-60a6-4031-9b46-c0a49ec4e693
    latitude DECIMAL(18,4) NULL,
    -- column_id: 095e4733-2d13-4199-9278-1487e6222f8d
    longitude DECIMAL(18,4) NULL,
    -- column_id: 1de4a923-4f48-40f9-b3ea-8397ba2a55b7
    install_date DATETIME NULL,
    -- column_id: 44b8f281-e222-4b97-9599-59f3882c7e8d
    is_operational BOOLEAN NULL,
    -- column_id: d5cb1856-3308-43a6-a3b3-9a98fcbbc068
    is_24_hour BOOLEAN NULL,
    -- column_id: 00fb4f51-829c-4cc3-9401-4361f38a19ee
    is_deposit_enabled BOOLEAN NULL,
    -- column_id: c2b3e397-dbf1-49ff-8c3c-c7004419b701
    is_cash_only BOOLEAN NULL,
    -- column_id: e3418bf4-054e-4e79-a446-f7f2cee47232
    max_withdrawal_amount DECIMAL(18,4) NULL,
    -- column_id: 663bd8c3-380e-4528-90ce-d3001fd49835
    daily_transaction_limit BIGINT NULL,
    -- column_id: 19ac1f52-0ad0-4bd2-b62b-d3fc82a19fd0
    avg_daily_transactions BIGINT NULL,
    -- column_id: 3bfe4d73-3934-4b50-9abd-2f4704f4d5b8
    cash_capacity STRING NULL,
    -- column_id: cae58ba4-8fd0-48f6-8652-7bb4f8e43c3f
    last_refill_date DATETIME NULL,
    -- column_id: bc6c44bb-8888-4d7f-98a4-767c14c685bf
    last_maintenance_date DATETIME NULL,
    -- column_id: 726a9e0f-ccc9-44cf-8ee8-b8b99ba3ab48
    surcharge_fee DECIMAL(18,4) NULL,
    -- column_id: 486bc7c9-ac8f-49aa-910d-dcfc16f01c47
    has_camera BOOLEAN NULL,
    -- column_id: 63374c49-65a0-4cb0-ba2a-eb997a2f49fc
    branch_id BIGINT NULL,
    -- column_id: 5c0ebee7-0add-4d5c-a81f-b53672aafaee
    created_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(atm_id)
DISTRIBUTED BY HASH(atm_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
