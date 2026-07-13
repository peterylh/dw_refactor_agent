-- ODS mirror of Apache Fineract m_wc_loan_delinquency_action (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_delinquency_action;
-- table_id: 004afd02-91a3-4673-95c6-82070e1f5f49
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_delinquency_action (
    -- column_id: dd415885-6ff3-4888-8886-afcc17848d82
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 651a0c66-ee08-46fe-9f35-5812b2b4151d
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: b7ca9f64-6d75-41d9-9f39-86ac3440b1b9
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 7a4b5d44-afd0-4323-9dc7-38cecb18beae
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 7a4f6651-6681-44a7-b6c4-def93ead5e76
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: abd018d7-e2d0-47c8-b7c4-bc552f92d122
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 28b9d411-ef6e-48e1-948f-02b1b6d04563
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 6c6c1450-67d4-4055-8a1b-1f977a4fbd22
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 79e3e9b0-01a8-4219-9abf-febb320c50f6
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: f17e9588-9b5a-44cb-82fb-973bac78800b
    `minimum_payment` DECIMAL(19,6) NULL COMMENT 'Fineract source column minimum_payment',
    -- column_id: dfd6b080-d229-420d-98ce-b7e58f5442a9
    `minimum_payment_type` VARCHAR(50) NULL COMMENT 'Fineract source column minimum_payment_type',
    -- column_id: c9975d56-60ae-4477-b768-f62f37d86fcc
    `frequency` INT NULL COMMENT 'Fineract source column frequency',
    -- column_id: eb282481-b246-4987-b0d1-a24320a74ac7
    `frequency_type` VARCHAR(50) NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: dc9accc3-92f1-4192-b4fd-141a2c15e665
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
