DROP TABLE IF EXISTS finance_analytics_dm.dwd_merchants;
-- table_id: 75cbd319-a1ec-4fef-8f88-87f877b70800
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_merchants (
    -- column_id: 6cf59fae-458d-4734-a98d-c0846a1ff16f
    merchant_id BIGINT NULL,
    -- column_id: 858ee345-c284-468e-957c-9f3fdc0faaa9
    merchant_name STRING NULL,
    -- column_id: 09dcf555-b1c2-40b6-8254-2aafa8e766c0
    category STRING NULL,
    -- column_id: 2db34b7e-20ab-4da7-9be1-16876a86cee8
    mcc_code STRING NULL,
    -- column_id: 5202cf8e-7583-49a0-90af-e562becccf07
    category_group STRING NULL,
    -- column_id: ed1b615c-96ca-4f90-af35-60368dc1c2ed
    city STRING NULL,
    -- column_id: e845eade-d2a5-43cf-bd4f-653a0ba114c6
    state STRING NULL,
    -- column_id: 685360c1-382e-4cdb-bb11-21030a281146
    country STRING NULL,
    -- column_id: 09a5e095-7ee8-469a-8201-f8d63c30f1d6
    latitude DECIMAL(18,4) NULL,
    -- column_id: 46bde391-ecd2-4f00-ab11-e4032db50545
    longitude DECIMAL(18,4) NULL,
    -- column_id: 72de4d54-a507-44af-8fd5-470a84c85d69
    region STRING NULL,
    -- column_id: 2ceb12df-07e8-456a-baad-1a58f11eb161
    risk_rating STRING NULL,
    -- column_id: 23866bf4-cc42-4898-acf2-0f0ce8274898
    risk_score DECIMAL(18,4) NULL,
    -- column_id: 7e6cc40f-4930-4dbe-b9b9-d7db14adc17e
    avg_transaction_amount DECIMAL(18,4) NULL,
    -- column_id: 4b49163e-dbeb-49a2-8688-9d645c7c0ef8
    transaction_value_segment STRING NULL,
    -- column_id: 93c751a7-f40f-42b1-ad89-054ec6dddcae
    is_online BOOLEAN NULL,
    -- column_id: 70d7cab9-be59-4ff7-af4f-63a5838f0315
    merchant_type STRING NULL,
    -- column_id: c8381100-4c57-49a1-90a1-3f19ecf85207
    established_date DATETIME NULL,
    -- column_id: 09b21fea-cd10-4fd5-b9ac-0e708f10417d
    years_in_business STRING NULL,
    -- column_id: e5044da0-69c2-4c7c-b1ff-e36bdaea3c37
    business_maturity STRING NULL,
    -- column_id: 36e3e03f-ec3a-4c77-aec7-a7eebca14114
    mcc_category STRING NULL,
    -- column_id: 11609535-13a0-436e-adf3-2b93fc2fdde6
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(merchant_id)
DISTRIBUTED BY HASH(merchant_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
