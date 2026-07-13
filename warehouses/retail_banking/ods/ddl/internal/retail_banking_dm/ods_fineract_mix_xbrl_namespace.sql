-- ODS mirror of Apache Fineract mix_xbrl_namespace (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_mix_xbrl_namespace;
-- table_id: 9d75de3f-09b3-4be0-b9e2-6ebc524db93d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_mix_xbrl_namespace (
    -- column_id: 83fbe7ea-8b0b-42b3-bcf4-35f06d3ed91c
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 12383738-eab4-4c13-b41d-43976719de53
    `prefix` VARCHAR(20) NOT NULL COMMENT 'Fineract source column prefix',
    -- column_id: 70bb6b4d-6b25-4640-92a4-6062321f8776
    `url` VARCHAR(100) NULL COMMENT 'Fineract source column url',
    -- column_id: 6929a225-1d45-45b4-a650-714242de1f8e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
