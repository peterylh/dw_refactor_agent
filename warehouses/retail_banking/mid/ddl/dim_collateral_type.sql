-- DIM generated from m_collateral_management
DROP TABLE IF EXISTS retail_banking_dm.dim_collateral_type;
-- table_id: d6e68c76-3db6-480e-9618-11facf0b97dd
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_collateral_type (
    -- column_id: e8dfe9e2-c4e8-491b-bb23-e135dadeba3f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3bdca85b-1223-4624-8a4d-c7679574c097
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 5694f5a3-9859-4154-8f57-9d9df60fb7bd
    `quality` VARCHAR(40) NOT NULL COMMENT 'Fineract source column quality',
    -- column_id: 247930d3-a7e1-46f6-8941-f52673a702eb
    `base_price` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column base_price',
    -- column_id: 4f22c64f-805c-4d09-a999-48164a3774f6
    `unit_type` VARCHAR(10) NOT NULL COMMENT 'Fineract source column unit_type',
    -- column_id: f2171d6f-ed9b-4f89-9e55-22d83d514a87
    `pct_to_base` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column pct_to_base',
    -- column_id: 37cff9cd-9b30-440a-9658-49bf4085812d
    `currency` BIGINT NULL COMMENT 'Fineract source column currency',
    -- column_id: ebd04bbe-813b-4630-b3a4-18cf64adc4bc
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
