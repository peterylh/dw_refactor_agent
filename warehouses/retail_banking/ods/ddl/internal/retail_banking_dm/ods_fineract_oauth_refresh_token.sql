-- ODS mirror of Apache Fineract oauth_refresh_token (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_oauth_refresh_token;
-- table_id: e134fe53-f41a-46a7-858e-f749c286214d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_oauth_refresh_token (
    -- column_id: 48fb63a4-f895-4df0-8d8c-d89cc3b3eb2f
    `token_id` VARCHAR(256) NULL COMMENT 'Fineract source column token_id',
    -- column_id: dd7dbad7-7e92-46ac-b2e9-8bb6a067252a
    `token` STRING NULL COMMENT 'Fineract source column token',
    -- column_id: 0b7ae495-9ac1-445a-b650-88e4d932168c
    `authentication` STRING NULL COMMENT 'Fineract source column authentication',
    -- column_id: 6b3713ae-5bdb-4f24-9cb5-643d07de9699
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`token_id`)
DISTRIBUTED BY HASH(`token_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
