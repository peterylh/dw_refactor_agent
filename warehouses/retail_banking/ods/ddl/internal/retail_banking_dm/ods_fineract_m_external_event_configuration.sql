-- ODS mirror of Apache Fineract m_external_event_configuration (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_event_configuration;
-- table_id: f543be0b-1b6c-45f0-911e-dfba394263f2
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_event_configuration (
    -- column_id: b1bbecb0-a3f4-402b-b560-baf90725bec5
    `type` VARCHAR(100) NOT NULL COMMENT 'Fineract source column type',
    -- column_id: 6fdf0e92-21ef-4bcc-98ec-8c7fc440aca4
    `enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column enabled',
    -- column_id: 98f71164-2c70-4e09-aed3-4b75a35a1e0d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`type`)
DISTRIBUTED BY HASH(`type`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
