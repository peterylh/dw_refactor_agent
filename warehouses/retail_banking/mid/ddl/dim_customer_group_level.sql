-- DIM generated from m_group_level
DROP TABLE IF EXISTS retail_banking_dm.dim_customer_group_level;
-- table_id: 10f21efe-22cc-41d8-a3d7-902909e08efb
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_customer_group_level (
    -- column_id: 699a76a0-8c4b-4b79-a869-8a37c88c676a
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8d8861a0-d8fb-499f-806b-2ff3377a6cc7
    `parent_id` INT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: c6d5e277-3605-4617-8296-02bbeb8920f9
    `super_parent` BOOLEAN NOT NULL COMMENT 'Fineract source column super_parent',
    -- column_id: f7b9d745-e3a6-4b2b-bd2d-920dd8761924
    `level_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column level_name',
    -- column_id: f0677c03-02bf-498f-971e-e709c1b10ff9
    `recursable` BOOLEAN NOT NULL COMMENT 'Fineract source column recursable',
    -- column_id: b771a3e6-a7b8-4204-b3b8-3177531ea7e9
    `can_have_clients` BOOLEAN NOT NULL COMMENT 'Fineract source column can_have_clients',
    -- column_id: 767409d6-3e07-4e0c-b8d5-62011d5f6274
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
