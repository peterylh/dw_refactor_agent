-- ODS mirror of Apache Fineract oauth_client_details (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_oauth_client_details;
-- table_id: d99671f4-7dee-4a77-b253-b6fe13440325
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_oauth_client_details (
    -- column_id: 2ca8d13f-8548-4f5d-aa97-524f24ecbc56
    `client_id` VARCHAR(128) NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: e9e07126-ca7f-4c2d-b248-1cb5d8ba79e5
    `resource_ids` VARCHAR(256) NULL COMMENT 'Fineract source column resource_ids',
    -- column_id: 4a15192c-f698-4118-9b74-b11b497ab1f3
    `client_secret` VARCHAR(256) NULL COMMENT 'Fineract source column client_secret',
    -- column_id: 8044e13d-c1c9-4861-86a7-6903a3d95ed2
    `scope` VARCHAR(256) NULL COMMENT 'Fineract source column scope',
    -- column_id: e5a0df69-c2f1-4ea3-9dad-cd1aad0ccf6d
    `authorized_grant_types` VARCHAR(256) NULL COMMENT 'Fineract source column authorized_grant_types',
    -- column_id: ccfa6eae-5718-443c-829f-a47f160ac677
    `web_server_redirect_uri` VARCHAR(256) NULL COMMENT 'Fineract source column web_server_redirect_uri',
    -- column_id: acf78850-24ee-4b6a-a4f4-a7db8974216c
    `authorities` VARCHAR(256) NULL COMMENT 'Fineract source column authorities',
    -- column_id: 1216d051-2fc2-475f-a8a9-d9c8aae94ea5
    `access_token_validity` INT NULL COMMENT 'Fineract source column access_token_validity',
    -- column_id: d416ec4e-48eb-4e06-87da-040e4d03d802
    `refresh_token_validity` INT NULL COMMENT 'Fineract source column refresh_token_validity',
    -- column_id: 1d06ebd3-b9fe-4f6d-9dd5-cc05afb94a87
    `additional_information` VARCHAR(4096) NULL COMMENT 'Fineract source column additional_information',
    -- column_id: cc23efc3-4d43-415c-8719-f96f1856eb1b
    `autoapprove` BOOLEAN NULL COMMENT 'Fineract source column autoapprove',
    -- column_id: c97413a3-2642-4a9a-99ff-6a5896b4ac4e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`client_id`)
DISTRIBUTED BY HASH(`client_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
