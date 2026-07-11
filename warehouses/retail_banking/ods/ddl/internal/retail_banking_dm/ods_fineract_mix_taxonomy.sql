-- ODS mirror of Apache Fineract mix_taxonomy (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_mix_taxonomy;
-- table_id: 48587429-32c4-4485-872f-1866784b2b49
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_mix_taxonomy (
    -- column_id: 6642695c-187e-449e-846e-ba091c0015f6
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b5e51642-95a4-4df9-98ac-485074ff78f5
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 5dfb4c49-1617-40ed-926a-b3dd554fb9ed
    `namespace_id` INT NULL COMMENT 'Fineract source column namespace_id',
    -- column_id: 66616583-73f9-48d0-86f7-057fbdb01fd7
    `dimension` VARCHAR(100) NULL COMMENT 'Fineract source column dimension',
    -- column_id: c5711579-85c8-48f8-a26d-4588057b1ce5
    `type` INT NULL COMMENT 'Fineract source column type',
    -- column_id: bcf6e8b7-08f4-4170-8502-ad03040cc7e4
    `description` VARCHAR(1000) NULL COMMENT 'Fineract source column description',
    -- column_id: 68630c22-4358-46e1-9059-7e4a824874c7
    `need_mapping` BOOLEAN NULL COMMENT 'Fineract source column need_mapping',
    -- column_id: 4aa9e622-9b45-46f4-93fa-fbb10554287a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
