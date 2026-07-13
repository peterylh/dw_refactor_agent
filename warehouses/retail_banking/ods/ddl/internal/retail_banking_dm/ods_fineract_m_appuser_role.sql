-- ODS mirror of Apache Fineract m_appuser_role (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_appuser_role;
-- table_id: 57807a82-2339-47d9-935d-e8c4caa80412
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_appuser_role (
    -- column_id: cdb0bd4b-4fef-4ecc-9b1a-1bc78fcf6bcd
    `appuser_id` BIGINT NOT NULL COMMENT 'Fineract source column appuser_id',
    -- column_id: d200d53f-fd36-405c-8589-81c15dbf71cf
    `role_id` BIGINT NOT NULL COMMENT 'Fineract source column role_id',
    -- column_id: 8a45167d-faea-4838-9c11-1c97cb424371
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`appuser_id`, `role_id`)
DISTRIBUTED BY HASH(`appuser_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
