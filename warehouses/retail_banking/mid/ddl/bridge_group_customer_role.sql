-- DWD generated from m_group_roles
DROP TABLE IF EXISTS retail_banking_dm.bridge_group_customer_role;
-- table_id: 6fb0fef5-77e8-46e5-83d0-df9df67e69a8
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_group_customer_role (
    -- column_id: c4e1dbff-7361-407a-bb94-4e1c3674326c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5e5d0f30-c9a5-45ff-8277-8d8b99018557
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 28dfd947-9709-4c5c-85f4-be82fb20de8f
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 0202b4d8-bd15-4039-a09b-3b61bb27f2fc
    `role_cv_id` INT NULL COMMENT 'Fineract source column role_cv_id',
    -- column_id: f83083d0-dfb4-4f86-9b27-5a1d39c0e99d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
