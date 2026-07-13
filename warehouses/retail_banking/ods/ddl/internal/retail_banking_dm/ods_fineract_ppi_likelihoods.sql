-- ODS mirror of Apache Fineract ppi_likelihoods (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_ppi_likelihoods;
-- table_id: ee305375-25c1-4515-bc3b-a4a6c782ee87
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_ppi_likelihoods (
    -- column_id: 7e7020b0-939a-4049-bb7c-8896a4fd5a7d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4c891c55-e691-4529-a960-a1213f9d94e0
    `code` VARCHAR(100) NOT NULL COMMENT 'Fineract source column code',
    -- column_id: ad2513d4-1e7c-4323-a256-7f5c6fbb4c7e
    `name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 84acbd26-de28-4b87-a15f-d1d55501f9dd
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
