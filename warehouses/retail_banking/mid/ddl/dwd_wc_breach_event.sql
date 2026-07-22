SET allow_partition_column_nullable = true;

-- DWD generated from m_wc_loan_breach_action
DROP TABLE IF EXISTS retail_banking_dm.dwd_wc_breach_event;
-- table_id: 737b32a9-ef47-4b04-bf58-02994258f259
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_wc_breach_event (
    -- column_id: 7a311099-c44c-4322-9dc5-0e2df0feec17
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e3318239-0312-4b70-a395-dfef93f81f1b
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 11455917-68c4-4c32-8455-6d6539631e62
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 460cec9e-bb59-4d3b-9630-8ea529db27ec
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 3ccb3b43-4ffc-4a30-a83b-8b301a02e29c
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 2ccae2b5-f6b5-464a-bfba-acb6ccfa9700
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: af697fd9-2551-4e38-8065-7c25b1fdef98
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 709b7830-902e-48a3-8644-609240e61458
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: d2b46c7d-4ae1-4742-8ba9-299f77614b4c
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c286a865-5889-448f-8b79-3535b893cc13
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 31f60931-78a1-49c2-b259-e6c3f757ad78
    `minimum_payment` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_payment',
    -- column_id: df690032-0917-486d-b5ed-20371034a5d6
    `minimum_payment_type` VARCHAR(50) NULL COMMENT 'Fineract source column minimum_payment_type',
    -- column_id: ca1b7cd4-19fe-4e17-ac2f-214826f10afe
    `frequency` INT NULL COMMENT 'Fineract source column frequency',
    -- column_id: 9799897d-4eb4-4bb6-9339-509fc95423ee
    `frequency_type` VARCHAR(50) NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: c992df0c-fadd-441b-b404-e579a4eee4c0
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
