-- ODS mirror of Apache Fineract m_wc_loan_originator_mapping (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_originator_mapping;
-- table_id: 4a37c893-9b5c-44be-a1db-bfe25e37c013
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_originator_mapping (
    -- column_id: 6f156658-f460-4169-98d4-c412f1617232
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cabf5592-46e6-4711-9f8e-3ebfa90b072f
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 754b826c-3f5f-4bfd-b4c0-db7997849854
    `originator_id` BIGINT NOT NULL COMMENT 'Fineract source column originator_id',
    -- column_id: 5673c53a-43ce-467f-a63b-20260fadbc01
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 445c7dd6-10e2-45f6-96de-219cdc22940e
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 0e890f56-65d5-43b1-a00f-b7f7630a37c0
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 08f483a6-0801-4536-9793-69f1eb5a1c9c
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: bbc67a0a-3202-440a-b461-8c4f870f504f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
