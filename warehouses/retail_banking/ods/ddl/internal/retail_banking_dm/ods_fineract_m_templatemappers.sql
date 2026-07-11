-- ODS mirror of Apache Fineract m_templatemappers (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_templatemappers;
-- table_id: 0b4c91d0-bd09-4e93-bf75-d6aa1cc3a891
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_templatemappers (
    -- column_id: 6198a0ad-2199-42b4-a1c2-c8eca4bd6836
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5564eb00-3ff5-4b19-8c01-d8c4349d154d
    `mapperkey` VARCHAR(255) NULL COMMENT 'Fineract source column mapperkey',
    -- column_id: 3cf4cb81-b66f-4a81-8053-910bff4ccc43
    `mapperorder` INT NULL COMMENT 'Fineract source column mapperorder',
    -- column_id: 78d2be1f-c97b-4f6f-b6c3-1457ac36a900
    `mappervalue` VARCHAR(255) NULL COMMENT 'Fineract source column mappervalue',
    -- column_id: a0fe2678-990c-40ff-b076-b05c71a2f0d8
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
