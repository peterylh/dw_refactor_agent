-- ODS mirror of Apache Fineract mix_taxonomy_mapping (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_mix_taxonomy_mapping;
-- table_id: 9a7cda0c-660e-47dd-a9fb-39f2b009e0a9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_mix_taxonomy_mapping (
    -- column_id: df29007e-051a-4c05-b99d-893379cbe3da
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cabd8445-3139-48d6-915d-299b9c84b93a
    `identifier` VARCHAR(50) NOT NULL COMMENT 'Fineract source column identifier',
    -- column_id: 8ef42300-c568-43f7-a6ae-086f753bb43a
    `config` VARCHAR(200) NULL COMMENT 'Fineract source column config',
    -- column_id: a69a157b-af7d-4f69-8d1d-116610f32eb1
    `last_update_date` DATETIME NULL COMMENT 'Fineract source column last_update_date',
    -- column_id: ea676542-f09d-428b-815d-991bedbbd98a
    `currency` VARCHAR(11) NULL COMMENT 'Fineract source column currency',
    -- column_id: 8e2efe83-6c5a-4c85-be33-c9506115455d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
