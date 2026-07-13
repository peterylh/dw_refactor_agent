-- ODS mirror of Apache Fineract oauth_access_token (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_oauth_access_token;
-- table_id: 8c8af3d3-4a46-4e26-817d-2754b36f8f80
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_oauth_access_token (
    -- column_id: 4f239d58-8ad8-49f2-9c4b-1bf70480c394
    `token_id` VARCHAR(256) NULL COMMENT 'Fineract source column token_id',
    -- column_id: edc87f01-5830-4294-a10f-292ff2d8c03c
    `token` STRING NULL COMMENT 'Fineract source column token',
    -- column_id: 2fd3099f-121a-4aa0-bde7-c30b1a452cd5
    `authentication_id` VARCHAR(256) NULL COMMENT 'Fineract source column authentication_id',
    -- column_id: 24e7655e-21aa-4687-b87a-792e836ce8ab
    `user_name` VARCHAR(256) NULL COMMENT 'Fineract source column user_name',
    -- column_id: 9ec91268-dfb4-4aaa-b4b1-67445a776f7b
    `client_id` VARCHAR(256) NULL COMMENT 'Fineract source column client_id',
    -- column_id: cceaf0ae-8adc-4cbd-bc31-19edda1b8d6d
    `authentication` STRING NULL COMMENT 'Fineract source column authentication',
    -- column_id: ed96af33-36c8-4d9f-b837-a144ab378f81
    `refresh_token` VARCHAR(256) NULL COMMENT 'Fineract source column refresh_token',
    -- column_id: 148f342f-7091-47b7-9bf8-338855925600
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`token_id`)
DISTRIBUTED BY HASH(`token_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
