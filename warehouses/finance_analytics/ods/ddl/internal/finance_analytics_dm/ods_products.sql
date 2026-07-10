DROP TABLE IF EXISTS finance_analytics_dm.ods_products;
-- table_id: c8da86d3-715a-438f-87f1-5f53136e6274
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_products (
    -- column_id: 3a850dbb-e8c4-4175-ab18-55462a58a45d
    product_id BIGINT NULL,
    -- column_id: d1fb6181-f5ba-49b4-8236-918bedb39147
    product_name STRING NULL,
    -- column_id: 832b0b9b-010a-4b86-959a-031e3ed5cd21
    category STRING NULL,
    -- column_id: f0fb85b5-c539-4da3-8774-755329f2c582
    interest_rate DECIMAL(18,4) NULL,
    -- column_id: e043b22c-20b0-41d8-86cc-43596cdd9f32
    min_balance DECIMAL(18,4) NULL,
    -- column_id: 6b2f604b-d291-47a2-a673-920fba8997c2
    monthly_fee DECIMAL(18,4) NULL,
    -- column_id: a44e0213-5d9c-4a1a-8100-55fbc81c0ef1
    overdraft_limit DECIMAL(18,4) NULL,
    -- column_id: 37b1d8a8-ab04-46fe-beae-977fb88fbe80
    product_tier STRING NULL,
    -- column_id: f65e4a3e-66e4-4beb-a281-25908e78ce97
    is_premium BOOLEAN NULL,
    -- column_id: 52c48374-de32-495f-b1d0-299c67600983
    created_at DATETIME NULL,
    -- column_id: a5bf6c3c-7345-44db-a681-7bf13f01f9f8
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
