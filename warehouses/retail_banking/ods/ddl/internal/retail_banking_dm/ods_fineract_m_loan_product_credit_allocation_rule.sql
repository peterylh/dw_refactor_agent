-- ODS mirror of Apache Fineract m_loan_product_credit_allocation_rule (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_product_credit_allocation_rule;
-- table_id: a9e5df4f-6178-4c17-92ba-90c7568a7b74
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_product_credit_allocation_rule (
    -- column_id: 5039c56b-32a4-416c-bdda-a27c8f67dec3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 82b7123e-db97-4b7d-b062-2f58a657b599
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: da57ec24-eb36-473f-be0a-7f2901fd57be
    `transaction_type` VARCHAR(255) NOT NULL COMMENT 'Fineract source column transaction_type',
    -- column_id: ff0f54b4-f363-45c4-89e8-e20e98e8f193
    `allocation_types` STRING NOT NULL COMMENT 'Fineract source column allocation_types',
    -- column_id: c2ade063-9bb5-4545-938c-9b1160b5c327
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7d96ab15-d590-42cb-b331-7cb3ea9161dc
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 37d4797f-748d-4163-a343-6581bcda7535
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 8fe459b8-5d16-4c5a-916f-fd76f066d660
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 852afe93-9904-46de-8bd4-08231b5c89b6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
