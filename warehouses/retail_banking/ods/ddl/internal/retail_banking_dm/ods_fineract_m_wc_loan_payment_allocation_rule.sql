-- ODS mirror of Apache Fineract m_wc_loan_payment_allocation_rule (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_payment_allocation_rule;
-- table_id: c68a796f-dea2-42ed-97c9-6126947b0886
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_payment_allocation_rule (
    -- column_id: c1335486-7758-4f09-ab78-dddbe54c5f68
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5c7849b4-58e4-44be-8a62-2aae4dcd9b70
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: cd03889f-bf74-49c6-ae19-f62733cbd589
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: 4103dbf4-bcc1-4ed1-a081-188972e59cb1
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: d2113882-a14c-430e-9f5a-4e7ab40856dd
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 9a6a7e6c-bf3e-47af-a726-8572e6ddf98b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: fe77b9b1-2499-407e-8de7-7faa6e2076b4
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 2962ad5b-0fbc-4f70-b23b-6d6908e01f7d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 18712092-f930-40da-87c9-6df5f24e8ae1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
