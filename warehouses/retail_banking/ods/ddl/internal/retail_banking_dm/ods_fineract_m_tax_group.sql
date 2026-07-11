-- ODS mirror of Apache Fineract m_tax_group (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_tax_group;
-- table_id: 47911fb3-7a85-4795-b6e6-d322733a6bed
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_tax_group (
    -- column_id: f8db56bc-5624-4c25-ab0e-b4ea3ffcb4ce
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4b6f1af8-4cfa-4f60-94e1-e798b2695d21
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: e3fc270d-d9b4-4a74-8eb4-eac29b5bd883
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 52ff7ad1-d9b6-40ea-88d0-7a554c2cafff
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: d45e067a-ec9d-407b-b990-8fc01eff3299
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 4f0cd62e-9ec8-4f2c-a4a8-a91f8e319e7f
    `lastmodified_date` DATETIME NOT NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: e7a3c1c9-bb5e-44e4-8327-1cf79f790044
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
