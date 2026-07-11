-- ODS mirror of Apache Fineract m_loan_transaction_repayment_schedule_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_transaction_repayment_schedule_mapping;
-- table_id: 0ef286c1-fb53-4ea9-9d61-9b4c9946bb8e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_transaction_repayment_schedule_mapping (
    -- column_id: 85fbc8c6-bea9-48ac-b77c-4f1075d8e5eb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 6e3a80c7-d8c8-492e-8c9c-37a9874c14e5
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: e80ac7ff-e5e5-40bb-814e-49375aa66834
    `loan_repayment_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_repayment_schedule_id',
    -- column_id: e32c5b1f-f2f1-4ade-b80b-57d4e8b7cc0c
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 64c250c2-3bdd-42d2-87c0-af9df024b51c
    `principal_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column principal_portion_derived',
    -- column_id: 8ce1f7b9-c11b-482d-8b8f-3d00b6b0ee58
    `interest_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column interest_portion_derived',
    -- column_id: 8cc5928f-aae0-4700-ac7a-cd7e03ebf2a5
    `fee_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column fee_charges_portion_derived',
    -- column_id: 0f4ead37-ad17-4455-8074-b521231e13ad
    `penalty_charges_portion_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column penalty_charges_portion_derived',
    -- column_id: 9c76944c-fd01-4d56-aa3c-b4844a3f864b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
