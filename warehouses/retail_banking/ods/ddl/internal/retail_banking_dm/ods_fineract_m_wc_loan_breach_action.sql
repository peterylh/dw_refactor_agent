-- ODS mirror of Apache Fineract m_wc_loan_breach_action (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_action;
-- table_id: bb3e9cf3-11e4-4609-83c2-74d97cd3f4e7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_action (
    -- column_id: 4d539a9e-cba8-4545-90a3-377e5790446e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 41697b2c-ea69-4aa6-97cf-af0daf5f60e8
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 64fe096d-d2ec-484e-816e-d234cc4250a3
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: d607d5c3-d2a2-43e9-83e1-466bcd08f44a
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 2cfa19e7-c436-4212-bf93-536c68c352e7
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: e8bd41ba-7e27-474e-9259-c14a4081a061
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 66987cb6-3a0c-4e81-88c8-4bda60cb6c99
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: df8614c0-d9c7-4d75-a4a8-071c20739c0d
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 9698dc44-9ffe-4448-b611-4ed8720f6ace
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c0c79f7c-9a54-46e7-8788-15788228adf5
    `minimum_payment` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_payment',
    -- column_id: e4dcbcb0-3de4-425c-8279-4582d25ca2f7
    `minimum_payment_type` VARCHAR(50) NULL COMMENT 'Fineract source column minimum_payment_type',
    -- column_id: df7e6ede-db35-4fd2-b19d-7e3dd35cbf0a
    `frequency` INT NULL COMMENT 'Fineract source column frequency',
    -- column_id: c8f5d31f-1a78-4930-946f-66d188ce3ee9
    `frequency_type` VARCHAR(50) NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: 30f90c8e-aa5a-4a0c-b2a7-610ec123aa08
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
