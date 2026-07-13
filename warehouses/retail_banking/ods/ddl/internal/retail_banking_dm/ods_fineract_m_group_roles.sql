-- ODS mirror of Apache Fineract m_group_roles (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_group_roles;
-- table_id: b0790c32-4ed9-4eee-ac9c-2636a10ab409
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_group_roles (
    -- column_id: 9f52e6e3-e1f6-440a-96b3-d7c54c2565f4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c61505fb-15e4-40ff-9d6e-2ce26a99f455
    `client_id` BIGINT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 624eb13e-7e33-4a28-aed9-fd7970ea241a
    `group_id` BIGINT NULL COMMENT 'Fineract source column group_id',
    -- column_id: ca1457b3-93a9-4f44-b505-7c0438bb83c9
    `role_cv_id` INT NULL COMMENT 'Fineract source column role_cv_id',
    -- column_id: 535e1acd-ee6a-4ef0-8f04-5ca7a6bfa1b8
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
