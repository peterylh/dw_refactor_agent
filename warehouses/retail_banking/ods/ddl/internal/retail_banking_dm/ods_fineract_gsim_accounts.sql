-- ODS mirror of Apache Fineract gsim_accounts (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_gsim_accounts;
-- table_id: d0d3ceb7-dffd-430e-b90d-ef33a91f31e9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_gsim_accounts (
    -- column_id: 167a8dc1-f660-4487-bfe2-9904b810ea66
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f64af11a-7dc0-49be-9b82-b4474df9e1ff
    `group_id` BIGINT NOT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 6576c244-4f3b-47b8-8740-5aa4cd4fcab2
    `account_number` VARCHAR(50) NOT NULL COMMENT 'Fineract source column account_number',
    -- column_id: 6e31e120-c5ad-4fc1-af03-5fde1b8285af
    `parent_deposit` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column parent_deposit',
    -- column_id: 1af28340-4788-42f2-8fde-6caca84be379
    `child_accounts_count` INT NOT NULL COMMENT 'Fineract source column child_accounts_count',
    -- column_id: e0813d02-0d8b-4612-a4c7-c9e5d6bb0dbc
    `accepting_child` BOOLEAN NOT NULL COMMENT 'Fineract source column accepting_child',
    -- column_id: 0ea1354a-db5d-4949-9f22-8bd76e0941fb
    `savings_status_id` SMALLINT NOT NULL COMMENT 'Fineract source column savings_status_id',
    -- column_id: 39a1aee7-f33b-4433-a131-447795c46b35
    `application_id` DECIMAL(10,0) NULL COMMENT 'Fineract source column application_id',
    -- column_id: f73a021d-5f7e-46ed-a157-f27c0c70774c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
