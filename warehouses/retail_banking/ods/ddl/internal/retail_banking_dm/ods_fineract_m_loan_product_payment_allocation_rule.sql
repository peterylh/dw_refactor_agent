-- ODS mirror of Apache Fineract m_loan_product_payment_allocation_rule (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_product_payment_allocation_rule;
-- table_id: 1ce1b227-3380-4307-bccd-48cbae5af7ee
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_product_payment_allocation_rule (
    -- column_id: d53f32a1-4589-4e08-9a91-12b964aa6f36
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0f95e944-67aa-486d-b6d0-6c145ab61736
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: a01de84e-d28a-4c7c-8345-3258f375c11b
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: c3478e89-d1bd-4e16-a01b-fb617a4891f0
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: cb06065f-7a42-4041-9508-c5840fb9bcb4
    `future_installment_allocation_rule` VARCHAR(255) NOT NULL COMMENT 'Fineract source column future_installment_allocation_rule',
    -- column_id: 88ac4c58-a24b-4d91-b9b5-7082f6acaf72
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 0f44a5e0-714f-46f0-94d5-7d33b24ad467
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8653fb2a-04d3-4387-9a99-6e0a26e14165
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: ea017254-01fb-4225-8dfc-9ba7a04b2a59
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c28aa52b-e7bf-4095-b306-93c7fc71379f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
