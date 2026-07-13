-- ODS mirror of Apache Fineract m_journal_entry_aggregation_summary (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_journal_entry_aggregation_summary;
-- table_id: 6cfe94b5-16e9-4f04-8979-8932d352b6a6
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_journal_entry_aggregation_summary (
    -- column_id: e22af6d2-4e0b-47cd-ac4d-49e5956c7d12
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 59ebfab1-06a6-492e-b8f4-9b8224b12873
    `gl_account_id` BIGINT NOT NULL COMMENT 'Fineract source column gl_account_id',
    -- column_id: 8c791025-1121-45ce-8fde-5e26e78c6ed4
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 617e7dd1-5ba3-4e04-9321-02661614f6f3
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 21a0c151-3037-4074-9034-f753cbe05083
    `entity_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column entity_type_enum',
    -- column_id: 638c4303-5636-42c6-8d28-fd0b6bfab18a
    `aggregated_on_date` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date',
    -- column_id: 878b73a1-b5cf-4ac9-aeb7-d54d771ac96f
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: a4db61f4-1a3e-4204-986e-7c100c95bd40
    `external_owner_id` BIGINT NULL COMMENT 'Fineract source column external_owner_id',
    -- column_id: ed4eb38d-5392-4a2f-a4ed-ef30caa82aaf
    `debit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column debit_amount',
    -- column_id: 4bcf07bf-16dd-4b7e-93c5-cd33f221d4f8
    `credit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column credit_amount',
    -- column_id: 9e689929-2ddb-4db2-b049-5152a6f9efe8
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: de3940bb-714e-4698-9f9b-6afb9d6554cf
    `job_execution_id` BIGINT NOT NULL COMMENT 'Fineract source column job_execution_id',
    -- column_id: c11855e8-d916-44f5-a12f-4f8c1a72a275
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: bc2fafc6-9b48-45bf-ac31-448391ed4d8d
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5fb49f2f-c597-4521-8a09-51cc43a92988
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 9f26050f-e935-4153-ad7f-2c525f90f2a2
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: e33f7a30-0683-4176-8931-19c3421531ff
    `originator_external_ids` VARCHAR(1000) NULL COMMENT 'Fineract source column originator_external_ids',
    -- column_id: 718e117c-bd62-4531-a745-a3f3e808e774
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
