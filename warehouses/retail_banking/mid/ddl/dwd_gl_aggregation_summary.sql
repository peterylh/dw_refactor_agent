-- DWD generated from m_journal_entry_aggregation_summary
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_aggregation_summary;
-- table_id: 653b8786-4003-454c-a8c4-3967231265a8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_aggregation_summary (
    -- column_id: bfac503f-2afe-44b8-93b6-c664ae7e569f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0341f745-d641-42b0-ad45-f6dfd1ae06e7
    `gl_account_id` BIGINT NOT NULL COMMENT 'Fineract source column gl_account_id',
    -- column_id: be5e5b4a-bc87-42e0-a57d-455245c0c455
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: cda63caa-f356-4de8-8750-d07ca87e5716
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: c3573d6c-93c7-460f-b255-790d44bc2e2f
    `entity_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column entity_type_enum',
    -- column_id: d440d87e-0ec6-49e7-801d-ee67a6a3c01b
    `aggregated_on_date` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date',
    -- column_id: ea9e9da0-209c-4c7a-ab0f-b38e73c7d19a
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: dea260ab-3dde-4eb0-a292-fede997ca86b
    `external_owner_id` BIGINT NULL COMMENT 'Fineract source column external_owner_id',
    -- column_id: 237612d1-5751-4408-aefd-1c7ff1dcd554
    `debit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column debit_amount',
    -- column_id: 3f63d8d3-86fd-4ce1-916e-fdc45a2aa130
    `credit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column credit_amount',
    -- column_id: 8bd885ce-ddf8-49e5-942b-55f1e3e619ee
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: ed2cc694-af07-4f6b-bf4c-6a527711e58e
    `job_execution_id` BIGINT NOT NULL COMMENT 'Fineract source column job_execution_id',
    -- column_id: 9076b675-e3b6-4746-b39f-a8243de3563a
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 92a34f02-7a22-4d8b-9a15-171eee48f175
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5ec9a994-75c1-4e21-80b5-9b09d401f1c6
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 4e15d5ab-3cf3-493a-a28e-abaa7a72ac7e
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: a8e32629-f967-4a1a-8525-6b379fa78901
    `originator_external_ids` VARCHAR(1000) NULL COMMENT 'Fineract source column originator_external_ids',
    -- column_id: 87993059-e11f-4c10-b089-28bc11e37311
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: d2d5d163-51ce-4e0a-be4f-5c73e8fe4650
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
