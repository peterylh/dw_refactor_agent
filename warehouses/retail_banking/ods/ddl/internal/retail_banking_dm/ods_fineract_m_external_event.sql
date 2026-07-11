-- ODS mirror of Apache Fineract m_external_event (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_event;
-- table_id: 7de96aef-8389-45ff-87fd-964c7ddeedaa
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_event (
    -- column_id: 00ca68a9-63c9-47b2-bfba-81d361fdff21
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c7253be6-d295-4746-a1c4-5ee7b940e78e
    `type` VARCHAR(100) NOT NULL COMMENT 'Fineract source column type',
    -- column_id: 44351362-c80f-4b15-a282-bc36847118ee
    `created_at` DATETIME NOT NULL COMMENT 'Fineract source column created_at',
    -- column_id: 974f474c-01c2-4432-8b33-79c7af2c2154
    `status` VARCHAR(100) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 78ffbc08-4f2a-45d6-99ce-a245900f1a42
    `business_date` DATE NOT NULL COMMENT 'Fineract source column business_date',
    -- column_id: 81e06be9-b7cf-4a78-ba21-a0df16d5d7a0
    `data` STRING NOT NULL COMMENT 'Fineract source column data',
    -- column_id: 8af318f3-1a3a-4b3b-995b-a93aca700d37
    `idempotency_key` VARCHAR(100) NOT NULL COMMENT 'Fineract source column idempotency_key',
    -- column_id: 56f604e6-94da-49dd-8a10-1aa03de16ca3
    `sent_at` DATETIME NULL COMMENT 'Fineract source column sent_at',
    -- column_id: 91ab5fc2-447c-4a4e-9abb-413e8cbb4db4
    `schema` VARCHAR(300) NOT NULL COMMENT 'Fineract source column schema',
    -- column_id: ede7fdcf-904c-408f-9a4e-863725789b67
    `category` VARCHAR(100) NOT NULL COMMENT 'Fineract source column category',
    -- column_id: dea8c628-f824-4dbe-817f-31127d7358c1
    `aggregate_root_id` BIGINT NULL COMMENT 'Fineract source column aggregate_root_id',
    -- column_id: fc941871-f5d9-4d47-8f6c-d76ac6c8aa09
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
