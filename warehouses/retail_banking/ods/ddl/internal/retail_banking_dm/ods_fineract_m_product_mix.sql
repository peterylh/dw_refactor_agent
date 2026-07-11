-- ODS mirror of Apache Fineract m_product_mix (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_mix;
-- table_id: 7679d7c1-269a-46d4-9b29-2f4e477b68e0
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_mix (
    -- column_id: 7e5661dc-915a-4d32-b5e9-cc5d2961087c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d248b64e-fe5a-47aa-8279-236b8542e927
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 96dd2602-1251-4a26-ad62-23df3778cc04
    `restricted_product_id` BIGINT NOT NULL COMMENT 'Fineract source column restricted_product_id',
    -- column_id: 4437925f-d258-40fb-ae2c-fe449c1e7072
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
