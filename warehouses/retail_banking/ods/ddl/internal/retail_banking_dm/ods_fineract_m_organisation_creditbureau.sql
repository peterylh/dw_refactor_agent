-- ODS mirror of Apache Fineract m_organisation_creditbureau (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_organisation_creditbureau;
-- table_id: bf66d95b-50c5-4b30-afae-bfdd65512070
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_organisation_creditbureau (
    -- column_id: 8172d0b3-c755-4824-82c2-0b3e4dfa10e4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e69d268b-1751-42ed-a48e-6988ccbdd0ca
    `alias` VARCHAR(50) NOT NULL COMMENT 'Fineract source column alias',
    -- column_id: 8cbfa7cc-07af-460a-bd8a-7b06a49ccbb0
    `creditbureau_id` BIGINT NOT NULL COMMENT 'Fineract source column creditbureau_id',
    -- column_id: ee17a515-c940-41b3-bbc9-b0f8f93042ab
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 4e0943b8-0ae2-4954-8d45-0c0c88b25801
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
