-- DIM generated from m_office
DROP TABLE IF EXISTS retail_banking_dm.dim_office;
-- table_id: 588243f7-50f5-4ed0-85d2-47f07c7a0071
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_office (
    -- column_id: 833b61ea-edff-48fc-a4f7-7a4c411c4e00
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 18c86214-f566-4f68-8701-9fb09fe8ffda
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: 2294e488-dc8f-4929-99cd-640012a7765d
    `hierarchy` VARCHAR(100) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: 8dd13db3-b49d-4165-80b7-54a7dcc05e1e
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 2c133c7b-c54f-412e-b8be-17147020083e
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 24372db5-26e0-43a6-b186-e5c15692b7f2
    `opening_date` DATE NOT NULL COMMENT 'Fineract source column opening_date',
    -- column_id: ee959b1e-1c79-4c87-a890-ed5a91655ec3
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
