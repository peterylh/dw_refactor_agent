-- DIM generated from m_rate
DROP TABLE IF EXISTS retail_banking_dm.dim_rate;
-- table_id: 2e61da92-fae4-43e8-84b8-91c7e0621656
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_rate (
    -- column_id: 2e3038c3-7166-4dca-bbc0-a8a06b406572
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 064257ab-a7f6-4293-ac04-712492d851a6
    `name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 36aaec62-d750-4cee-920b-a4a89fd7e505
    `percentage` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column percentage',
    -- column_id: a7bbe140-42fc-4e14-925b-d4a5c81ff03c
    `active` BOOLEAN NULL COMMENT 'Fineract source column active',
    -- column_id: 3102d144-235a-4207-9c3e-ee29ed261fe0
    `product_apply` SMALLINT NOT NULL COMMENT 'Fineract source column product_apply',
    -- column_id: 00e02a07-b57e-4543-82c9-6221b1fc3b8f
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 0993b3f9-2683-45ca-882e-0d4a69baefd5
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: c3fe9fbe-276d-452d-b614-05941ed0606b
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: b8db341a-343e-43be-ab28-1a9388752775
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: a04ae5e3-25e0-49fc-ab81-8f53ee6bf1b6
    `approve_user` BIGINT NULL COMMENT 'Fineract source column approve_user',
    -- column_id: 9c9253ab-6b58-41db-a929-08e5ec91bcf2
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
