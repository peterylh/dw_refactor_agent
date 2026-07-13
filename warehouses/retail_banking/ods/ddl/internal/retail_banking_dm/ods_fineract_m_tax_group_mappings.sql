-- ODS mirror of Apache Fineract m_tax_group_mappings (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_tax_group_mappings;
-- table_id: fc9972b0-b96f-4ebb-960b-99e980d8cf12
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_tax_group_mappings (
    -- column_id: deaa6944-8389-4440-a195-8eaee04eb846
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ebcca8e7-8f34-4887-af7f-9346704a196b
    `tax_group_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_group_id',
    -- column_id: fb3fac48-6e6f-4525-9225-cc127f8b9c69
    `tax_component_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_component_id',
    -- column_id: a59ff86d-2ff3-4c13-a187-63ddbf66c12b
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: f90cc2c6-9a68-4e8d-9a7f-0c79bfc85924
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: b955fb28-2e94-4c9a-8b52-96c426996313
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 064542f1-5bdf-48a8-b851-e4b08640b301
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: 5f32f485-2941-4f53-9fa3-e0d80d10bd4a
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 4f983646-d49e-4009-abab-b3ee63469653
    `lastmodified_date` DATETIME NOT NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 88f73e85-abd1-490f-aaa1-36758a19b6d6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
