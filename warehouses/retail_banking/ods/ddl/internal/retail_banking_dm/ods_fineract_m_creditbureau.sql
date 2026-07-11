-- ODS mirror of Apache Fineract m_creditbureau (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_creditbureau;
-- table_id: 889649a7-2472-493b-b28b-05e1c9a7b520
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_creditbureau (
    -- column_id: b91049c9-ad38-4da8-abc2-e95d06c8dd87
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6e946fe2-20fd-4d50-ab06-bcc790ed90c2
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 9e0a0aae-9c11-4ff8-b7c0-d90ea1e9c78d
    `product` VARCHAR(100) NOT NULL COMMENT 'Fineract source column product',
    -- column_id: db9eb9a3-9930-458f-8080-4b1179d1375e
    `country` VARCHAR(100) NOT NULL COMMENT 'Fineract source column country',
    -- column_id: bb80ad01-37d9-4428-aea4-634ed3c35b30
    `implementation_key` VARCHAR(100) NOT NULL COMMENT 'Fineract source column implementation_key',
    -- column_id: 8085eff1-e625-4cb8-8bc9-cf52ba7596c4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
