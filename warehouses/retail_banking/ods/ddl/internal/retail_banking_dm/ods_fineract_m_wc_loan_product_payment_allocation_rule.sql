-- ODS mirror of Apache Fineract m_wc_loan_product_payment_allocation_rule (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product_payment_allocation_rule;
-- table_id: 7b48b7b4-4175-429f-bb05-4a5df4e8fc59
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product_payment_allocation_rule (
    -- column_id: c75b6d18-72f3-4cd2-89c1-83220f8135a9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2aa82919-54ed-4e24-954e-558ac2011cee
    `wc_loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_product_id',
    -- column_id: c1443bed-3c21-4667-948b-a9f46fc6f8c8
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: cc78bf05-da77-4e6f-abd1-386bf2725f44
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: fd241842-70e6-465b-8784-2630baae30bc
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: b28cffcd-afc8-41a5-a1aa-7fa4c42c1005
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: ea27e700-b1df-42c8-afe9-5bb19ca29e29
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: ad3d7d8b-769c-46c7-ba78-19de2a918ee7
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 96dc984c-f320-411e-8b91-c03b7c98a88b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
