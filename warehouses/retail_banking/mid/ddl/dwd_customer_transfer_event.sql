SET allow_partition_column_nullable = true;

-- DWD generated from m_client_transfer_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_customer_transfer_event;
-- table_id: 34e5c645-3cd6-496c-9346-d646fe2eeda3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_customer_transfer_event (
    -- column_id: 12731d90-76e2-45f6-b6a2-a0915804da55
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9304ce0b-1505-4954-9f56-c6c6637ee249
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 92461096-bac5-4152-a043-24d94aa30db6
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 97c90458-8192-4973-bbec-93272968b263
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: f8c6116d-8ea1-4b73-9456-6feae5e08cb1
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 79ac7f8d-ed87-454a-997e-000c579845e0
    `proposed_transfer_date` DATE NULL COMMENT 'Fineract source column proposed_transfer_date',
    -- column_id: 8197bd78-719b-48c7-87df-bd2bdd08ddb8
    `transfer_type` TINYINT NOT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 63fcfcbf-fc54-4738-962b-629c85010c69
    `submitted_on` DATE NOT NULL COMMENT 'Fineract source column submitted_on',
    -- column_id: a2e94e38-2551-4703-8f60-d02afb09c53f
    `submitted_by` BIGINT NOT NULL COMMENT 'Fineract source column submitted_by',
    -- column_id: e12d028f-63cb-4995-bf13-858ae7cebaee
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
