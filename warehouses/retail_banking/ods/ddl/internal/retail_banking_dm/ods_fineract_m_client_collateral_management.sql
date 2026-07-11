-- ODS mirror of Apache Fineract m_client_collateral_management (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_collateral_management;
-- table_id: 4bea2ec0-7ef9-4973-a884-fda1a7a83d1d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_collateral_management (
    -- column_id: 6250adb2-3a76-4362-9cad-089e799aa104
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f88cf981-639e-4257-a5a4-f3509f1c1575
    `quantity` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column quantity',
    -- column_id: bf521df5-f7ba-4dc6-a332-3ed224eda465
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: afe2c1b6-665e-498f-8e5f-5ce0b6d6c69d
    `collateral_id` BIGINT NULL COMMENT 'Fineract source column collateral_id',
    -- column_id: 7338a9f7-ce28-44a3-96ff-7f8c12809081
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
