-- ODS mirror of Apache Fineract m_wc_loan_product_configurable_attributes (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product_configurable_attributes;
-- table_id: dc9f0048-8bd1-4de8-a120-8f0cf46a2830
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_product_configurable_attributes (
    -- column_id: ebfc1f54-2947-4d9e-96d2-740b3be182e7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b6401731-6c0a-483a-a58a-fc2d81267293
    `wc_loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_product_id',
    -- column_id: 13ce65bc-411b-4064-a680-5550ef30bac2
    `delinquency_bucket_classification_overridable` BOOLEAN NULL COMMENT 'Fineract source column delinquency_bucket_classification_overridable',
    -- column_id: ca42e928-e504-4db2-ad92-4f7e5d867c9d
    `discount_default_overridable` BOOLEAN NULL COMMENT 'Fineract source column discount_default_overridable',
    -- column_id: 6005ef31-2452-438d-9046-f8731fd3b46c
    `period_payment_frequency_overridable` BOOLEAN NULL COMMENT 'Fineract source column period_payment_frequency_overridable',
    -- column_id: 2a618634-2899-41b3-abfd-e3b6106e01af
    `period_payment_frequency_type_overridable` BOOLEAN NULL COMMENT 'Fineract source column period_payment_frequency_type_overridable',
    -- column_id: 525c615b-257f-44e7-8921-a5b4f459a21c
    `breach_overridable` BOOLEAN NULL COMMENT 'Fineract source column breach_overridable',
    -- column_id: 54f67303-5ff6-437b-9643-b21b6fa7dbaa
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
