-- ODS mirror of Apache Fineract m_loan_delinquency_tag_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_delinquency_tag_history;
-- table_id: 5ff39f0f-0ac2-438e-bdbb-b731c62844ff
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_delinquency_tag_history (
    -- column_id: 27e02a8a-797c-406e-b3df-f38cf31408d1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8f6652b2-2137-417d-8d27-925c829f4fff
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: 364720c7-aa29-4fa0-ac57-7dc9913e4b21
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: be8301de-b68f-4f54-b837-0c9025c2f887
    `addedon_date` DATE NOT NULL COMMENT 'Fineract source column addedon_date',
    -- column_id: 1c801e36-fa51-469e-97a8-7d9712575129
    `liftedon_date` DATE NULL COMMENT 'Fineract source column liftedon_date',
    -- column_id: 34226487-05b9-49fe-82ed-56ffba96502f
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 8d208888-bf49-4f2f-8131-05d99753b63d
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 55f9c9e6-bcec-491f-881f-80180d1df363
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 6349dcef-5e03-456c-92c8-bb97618b1e04
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 755efcf8-da04-468b-8049-d61538cc3795
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 5e76fc14-bdeb-4822-a6f5-7604da612e00
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
