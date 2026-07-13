-- ODS mirror of Apache Fineract m_wc_loan_period_payment_rate_change (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_period_payment_rate_change;
-- table_id: 4489fb64-99f5-4745-9090-0002613ce8ae
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_period_payment_rate_change (
    -- column_id: f097fac4-9c75-4d46-8274-8105021d5b6d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d6e0c950-d305-40bb-9907-182018a1108e
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 1d0fcfba-983e-40ce-98d6-466f1df75c9b
    `effective_date` DATE NOT NULL COMMENT 'Fineract source column effective_date',
    -- column_id: cb6c89fb-b398-496a-9d7a-241d8f94b243
    `previous_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column previous_rate',
    -- column_id: 7c7a29d6-1f0e-4baf-bb0e-d1cd48828347
    `new_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column new_rate',
    -- column_id: 7b0f0934-6bec-49d7-911d-fa9b88b3eed3
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 6e116087-3e0a-45e4-99eb-21725b49a862
    `reversed_on_date` DATE NULL COMMENT 'Fineract source column reversed_on_date',
    -- column_id: 53890992-1a9a-4686-8a19-2a1514a30512
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e59b3c69-cd9c-426e-8381-72aa0ec3bfe9
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: ada15e0f-db4e-4015-afae-9396a2075524
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: eedce486-379d-4d55-b61d-7e3ab151c97f
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 0b58ced2-c4ee-4039-bd69-c0f3a0b58560
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 2d611609-6b12-415b-9f2a-d0c8a03e25ca
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
