-- ODS mirror of Apache Fineract m_password_validation_policy (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_password_validation_policy;
-- table_id: fa9fc752-9597-4ec3-b55d-1149c8540159
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_password_validation_policy (
    -- column_id: a6c83dcb-e9c9-4d45-92cb-81d67a23df84
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f05c2ccc-71eb-4681-ac03-b43640157296
    `regex` STRING NOT NULL COMMENT 'Fineract source column regex',
    -- column_id: c382bc87-4557-4a12-8112-05110fec0d2c
    `description` STRING NOT NULL COMMENT 'Fineract source column description',
    -- column_id: a8ef6260-3650-4c69-a42d-49b1d0886ef5
    `active` BOOLEAN NOT NULL COMMENT 'Fineract source column active',
    -- column_id: 9c14fcfd-c0b4-4950-ba45-f523b06e0478
    `key` VARCHAR(255) NOT NULL COMMENT 'Fineract source column key',
    -- column_id: b3269c9a-86f2-41d9-8691-b73666da4de5
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
