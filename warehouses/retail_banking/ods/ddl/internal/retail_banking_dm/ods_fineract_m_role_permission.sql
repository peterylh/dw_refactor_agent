-- ODS mirror of Apache Fineract m_role_permission (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_role_permission;
-- table_id: 2139dfc0-8d27-479d-be8b-f466583ff72e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_role_permission (
    -- column_id: 3dc256a1-2715-4024-b2a7-51b12d206146
    `role_id` BIGINT NOT NULL COMMENT 'Fineract source column role_id',
    -- column_id: cd51e5b0-d63a-4bd3-9091-bbbc12690e18
    `permission_id` BIGINT NOT NULL COMMENT 'Fineract source column permission_id',
    -- column_id: c72e8795-62f5-440a-9385-7c0bb449e8b2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`role_id`, `permission_id`)
DISTRIBUTED BY HASH(`role_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
