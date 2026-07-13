-- DIM generated from m_surveys
DROP TABLE IF EXISTS retail_banking_dm.dim_survey;
-- table_id: add02e0d-6349-4b5b-9def-1822d6cc6cf0
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_survey (
    -- column_id: d77bb58d-8731-4245-8044-663ccdc5a476
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ff7987d9-0ac6-4124-9ecd-71ab4003211b
    `a_key` VARCHAR(32) NOT NULL COMMENT 'Fineract source column a_key',
    -- column_id: fa154d62-80b9-4076-86db-73f857e60d85
    `a_name` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_name',
    -- column_id: ae833cc8-4873-439c-9d5d-42cc5a0e3930
    `description` VARCHAR(4000) NULL COMMENT 'Fineract source column description',
    -- column_id: 21e5e2ef-59e6-43cc-8850-2ac9a513d0cd
    `country_code` VARCHAR(2) NOT NULL COMMENT 'Fineract source column country_code',
    -- column_id: b7c79f6d-7a74-43a9-a401-7ae8a324adf0
    `valid_from` DATE NULL COMMENT 'Fineract source column valid_from',
    -- column_id: ac673677-6f28-499c-ae19-3ae2a4983501
    `valid_to` DATE NULL COMMENT 'Fineract source column valid_to',
    -- column_id: d4cd29b9-57db-4ace-a6eb-1169d8701f42
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
