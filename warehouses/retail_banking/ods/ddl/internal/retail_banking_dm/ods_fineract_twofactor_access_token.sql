-- ODS mirror of Apache Fineract twofactor_access_token (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_twofactor_access_token;
-- table_id: d475a4d6-ee25-4c46-ac2f-9ee7382072ab
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_twofactor_access_token (
    -- column_id: 505b6c53-b96b-41b4-9ace-e8a3a2970179
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b4db1b71-bd7c-4deb-b022-72a74db1f650
    `token` VARCHAR(32) NOT NULL COMMENT 'Fineract source column token',
    -- column_id: 930e76e7-b746-404d-a6f9-a8d968b3e8da
    `appuser_id` BIGINT NOT NULL COMMENT 'Fineract source column appuser_id',
    -- column_id: eea84336-2dba-4afa-9654-080e1f13099f
    `valid_from` DATETIME NOT NULL COMMENT 'Fineract source column valid_from',
    -- column_id: 69aa1694-4aae-4e4b-b56f-66c4e6cbede8
    `valid_to` DATETIME NOT NULL COMMENT 'Fineract source column valid_to',
    -- column_id: 044098bc-624f-49f9-8285-1511cc878340
    `enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column enabled',
    -- column_id: f59cccc8-d5da-4c32-9a09-7545d7baa531
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
