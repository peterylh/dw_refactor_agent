-- DWD generated from m_loan_transaction_relation
DROP TABLE IF EXISTS retail_banking_dm.bridge_loan_transaction_relation;
-- table_id: 74444292-b589-4525-8c4c-2f6b3744a2f1
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_loan_transaction_relation (
    -- column_id: e277f0ce-20d7-4f5d-afbc-ee7bf1a18812
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ba4fdfa2-7d57-4b51-9f67-119e94833baa
    `from_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column from_loan_transaction_id',
    -- column_id: 8ca565c7-7a47-485c-b05b-d3618bc3b15b
    `to_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_loan_transaction_id',
    -- column_id: 1416cf1f-d953-4e57-bfbe-f6e729304e96
    `relation_type_enum` INT NOT NULL COMMENT 'Fineract source column relation_type_enum',
    -- column_id: ad289f0e-e9cf-43a5-b9be-7c1130357cc5
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: bb6f2a68-0af4-4453-8248-8a7ee361395b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 460c2f36-350b-4aac-a91b-22e5c98f16b4
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 402f76c3-1675-42c9-8f88-58a73c33002b
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 152253c7-3c82-40f1-8a61-d733cce3610f
    `to_loan_charge_id` BIGINT NULL COMMENT 'Fineract source column to_loan_charge_id',
    -- column_id: 2a6269f6-a267-4491-8365-46ba2be03718
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 05763702-74a3-439d-8922-dbe3d2225bb5
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
