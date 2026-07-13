-- ODS mirror of Apache Fineract m_share_product_market_price (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_product_market_price;
-- table_id: a8631e0f-aba2-437c-85d6-2e5ab8c91433
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_product_market_price (
    -- column_id: 9f70fac4-b1d0-4d33-8ae7-7cf9e60fe696
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6ac33f84-4ac6-47b4-b18c-5eb40376b81d
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 8b2a8cc4-c08c-4aa1-81e6-69bfc4868d40
    `from_date` DATE NULL COMMENT 'Fineract source column from_date',
    -- column_id: 9a5e5ab5-d1c0-4270-acd7-416171299de8
    `share_value` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column share_value',
    -- column_id: 3d6c9df4-ada4-41ac-8b49-ef8f63145a12
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
