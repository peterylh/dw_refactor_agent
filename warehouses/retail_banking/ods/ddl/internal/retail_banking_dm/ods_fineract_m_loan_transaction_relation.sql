-- ODS mirror of Apache Fineract m_loan_transaction_relation (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_transaction_relation;
-- table_id: 690f384e-78aa-4525-8750-ef84d1c658ac
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_transaction_relation (
    -- column_id: ae9d81c4-9c30-4e70-b906-2b6c6b673d2b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2996bb93-e9a3-4a03-ab78-8d31c5fc5750
    `from_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column from_loan_transaction_id',
    -- column_id: 7b1ed4dc-d3fb-4849-96af-c537b6f5be5a
    `to_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_loan_transaction_id',
    -- column_id: 8cbc0e69-cee1-4074-9645-077ca5053c21
    `relation_type_enum` INT NOT NULL COMMENT 'Fineract source column relation_type_enum',
    -- column_id: 215124ee-36e7-46b6-84ab-8ac7788c56f3
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 870300fc-9750-49f6-b27e-f9f19eb335b3
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: a0d6bf21-66fb-4092-8dff-895a9502712d
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: caf2b734-22b7-4f66-b272-5af10e4cc0a9
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 212b544e-af11-45cd-8d78-47185ac916b7
    `to_loan_charge_id` BIGINT NULL COMMENT 'Fineract source column to_loan_charge_id',
    -- column_id: 1d6a6f33-3c08-4bf2-beb6-7bda840469be
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
