-- DIM generated from m_creditbureau
DROP TABLE IF EXISTS retail_banking_dm.dim_credit_bureau;
-- table_id: d578b672-e15c-48c0-9cb6-e57eca7efeae
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_credit_bureau (
    -- column_id: bf538f26-25a0-4bbf-aa21-93e362cb573d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bd3bf2ab-28cb-4bd6-b5e9-ef1766d30d6e
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 88b9c066-f638-464c-9b7f-630130368b68
    `product` VARCHAR(100) NOT NULL COMMENT 'Fineract source column product',
    -- column_id: 8d2659eb-5119-41e3-94a2-9401303023c2
    `country` VARCHAR(100) NOT NULL COMMENT 'Fineract source column country',
    -- column_id: 42533591-805c-4428-baa3-7f0229c70595
    `implementation_key` VARCHAR(100) NOT NULL COMMENT 'Fineract source column implementation_key',
    -- column_id: d7398e65-3278-441a-88c3-13bd44ffab16
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
