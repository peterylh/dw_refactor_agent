-- ODS mirror of Apache Fineract request_audit_table (风险、合规与审计)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_request_audit_table;
-- table_id: 5269492a-e4ad-4a57-83e7-0f4101cc9ae1
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_request_audit_table (
    -- column_id: e652912e-c4a8-4e66-967d-7d56cd20b7cd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 44620b62-1020-419a-b23c-993ec89d3010
    `lastname` VARCHAR(100) NOT NULL COMMENT 'Fineract source column lastname',
    -- column_id: c26d5287-4525-4be3-8cf1-707c56b49217
    `username` VARCHAR(100) NOT NULL COMMENT 'Fineract source column username',
    -- column_id: 9a3b4806-e3ed-4c4d-8ba6-e661e1d52c48
    `mobile_number` VARCHAR(50) NULL COMMENT 'Fineract source column mobile_number',
    -- column_id: 4085603d-2f75-4110-b277-dcda6c06ff31
    `firstname` VARCHAR(100) NOT NULL COMMENT 'Fineract source column firstname',
    -- column_id: 7c1d88e5-4e79-45a9-8cf8-c6e212a0796c
    `authentication_token` VARCHAR(100) NULL COMMENT 'Fineract source column authentication_token',
    -- column_id: 72a43d1b-0ba4-48c8-a7c3-a6b1a0cd4057
    `password` VARCHAR(250) NOT NULL COMMENT 'Fineract source column password',
    -- column_id: 741ff8a1-60d8-4036-b7e5-23b335c8a87c
    `email` VARCHAR(100) NOT NULL COMMENT 'Fineract source column email',
    -- column_id: 89bffdb1-ec05-471c-adee-6a7dcd3e35ed
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 7fc73c41-cd9c-4f24-8415-e78d63cd3fb4
    `created_date` DATE NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: aeffd61b-c593-4616-b721-30dd3d425f76
    `account_number` VARCHAR(100) NOT NULL COMMENT 'Fineract source column account_number',
    -- column_id: e437b099-c069-4758-aa8f-11d6218d45be
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
