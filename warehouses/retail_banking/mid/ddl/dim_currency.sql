-- DIM generated from m_currency
DROP TABLE IF EXISTS retail_banking_dm.dim_currency;
-- table_id: fa0112a5-1603-47d0-9b7e-88437d2b3593
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_currency (
    -- column_id: 65b03c49-b387-4654-bc4a-636af41dfef3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: aea4ae99-a076-486b-9326-18a5737a9f37
    `code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column code',
    -- column_id: 2d18ab62-0eda-41ff-b6e2-bd673a8be595
    `decimal_places` SMALLINT NOT NULL COMMENT 'Fineract source column decimal_places',
    -- column_id: 154153c2-c60d-4982-92a4-5fdc7f95bfaa
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: bedcc5af-b413-4c6d-9c23-dcb80ff8f1ef
    `display_symbol` VARCHAR(10) NULL COMMENT 'Fineract source column display_symbol',
    -- column_id: 3b7afbb5-5ec2-4095-961f-3998a21fe9ac
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 32815db2-9a71-4243-b84a-943ee4fdf93e
    `internationalized_name_code` VARCHAR(50) NOT NULL COMMENT 'Fineract source column internationalized_name_code',
    -- column_id: c7db255a-09fa-47fd-aabe-18e499543a38
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
