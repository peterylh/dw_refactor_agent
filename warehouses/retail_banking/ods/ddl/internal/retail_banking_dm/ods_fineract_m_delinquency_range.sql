-- ODS mirror of Apache Fineract m_delinquency_range (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_delinquency_range;
-- table_id: 9002feb3-428e-4a9d-9e43-cce6c345d7b5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_delinquency_range (
    -- column_id: 2603d038-c423-4740-8746-27761c1ccadf
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 991cbe38-a530-4eef-a798-fc94280f2ee9
    `classification` VARCHAR(100) NOT NULL COMMENT 'Fineract source column classification',
    -- column_id: bcb9f9b8-5b56-4eba-b358-9a6de857790e
    `min_age_days` BIGINT NOT NULL COMMENT 'Fineract source column min_age_days',
    -- column_id: 14b7fcba-6ff7-4de5-b6b2-076a2f29f990
    `max_age_days` BIGINT NULL COMMENT 'Fineract source column max_age_days',
    -- column_id: 50697f62-6585-4ef2-b0bf-e9430741e0a4
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 6f72e8f0-ada9-4fca-b14c-fe3639fa9c68
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: de8d8954-98cb-469a-b0d3-00c0f983fea3
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: c5430299-e9ca-49fa-9a57-79a2ae2ef2aa
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e4e96cf0-f0d1-4c70-aa2f-bfd96aa4df87
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 79905500-221d-4696-ab67-a4c3d28b0653
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
