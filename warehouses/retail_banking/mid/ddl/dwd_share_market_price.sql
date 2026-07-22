SET allow_partition_column_nullable = true;

-- DWD generated from m_share_product_market_price
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_market_price;
-- table_id: f925edd7-7b26-4f3c-b903-20686bc1c6f8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_market_price (
    -- column_id: db9f9d0a-fc56-4af8-8def-d7b4220012e4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 72f1e6d5-0dc9-4238-8871-5466f8180197
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: cea4aa2c-bfd3-4547-b9a8-52bc08f083be
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 4d0c404f-2db4-4414-abad-ee5ab2678129
    `from_date` DATE NULL COMMENT 'Fineract source column from_date',
    -- column_id: 8f772ac2-40be-42a1-b058-548a155b07c4
    `share_value` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column share_value',
    -- column_id: 44b3ed61-b876-4c9e-abbb-b922cffcef80
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
