-- ODS mirror of Apache Fineract m_wc_delinquency_configuration (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_delinquency_configuration;
-- table_id: 9f679219-e506-4551-8b06-08338dd54dcc
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_delinquency_configuration (
    -- column_id: 557d7490-06e2-4266-ae03-41d9100963e1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 57f1b43b-2e95-4e03-a561-0f54b144ca21
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: a85198fb-ed93-4231-9c5f-2ed7fc5d8007
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 76cf4d63-650c-4452-bac7-73178aaefb83
    `bucket_id` BIGINT NOT NULL COMMENT 'Fineract source column bucket_id',
    -- column_id: c183e30c-856a-48e9-8a22-f6ef16c8b472
    `frequency` INT NOT NULL COMMENT 'Fineract source column frequency',
    -- column_id: 8b39877e-be3b-4f42-8bc2-43c39d837b84
    `frequency_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: 1bb44989-907a-4805-b191-33b9b4d23bf4
    `minimum_payment` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column minimum_payment',
    -- column_id: 97830665-2283-437c-951b-178923389929
    `minimum_payment_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column minimum_payment_type',
    -- column_id: 1e68ad59-a4e4-4c88-8ba0-3f008e249c01
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 51ffe3b7-c883-40dd-949f-848d0819209b
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: bde74142-9d04-483d-b596-6277dae800aa
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
