-- ODS mirror of Apache Fineract c_configuration (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_c_configuration;
-- table_id: fb3174c0-4389-466b-bce7-958ecb780e8b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_c_configuration (
    -- column_id: 3ab65903-776f-4c0b-b13f-2d5d4455e579
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2021236c-710c-4b9b-92f5-e3333077ad4f
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 1a57f25a-6a36-47b8-b23f-8edc5390fc98
    `value` INT NULL COMMENT 'Fineract source column value',
    -- column_id: 6adfd637-a781-4641-be3e-918613d069bf
    `date_value` DATE NULL COMMENT 'Fineract source column date_value',
    -- column_id: f7af0be0-8efc-4bc9-94a9-dbc9396107da
    `string_value` VARCHAR(100) NULL COMMENT 'Fineract source column string_value',
    -- column_id: fec9d0e5-e18d-47ac-a6aa-e1cad9f0bdd7
    `enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column enabled',
    -- column_id: 66ae5ffa-4f45-4ecb-8706-39da10f19318
    `is_trap_door` BOOLEAN NOT NULL COMMENT 'Fineract source column is_trap_door',
    -- column_id: 5ff0ed85-d67f-4b59-8064-b4e7a45bca1e
    `description` VARCHAR(300) NULL COMMENT 'Fineract source column description',
    -- column_id: 07998927-eee8-4732-bd03-69716a67859c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
