-- ODS mirror of Apache Fineract m_loan_progressive_model (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_progressive_model;
-- table_id: 1d01aadb-7037-4bc6-8e3b-b33760d1a021
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_progressive_model (
    -- column_id: 8f9f6a55-4f5e-40fc-8a95-9efa84838c63
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 33c7c610-6f78-40ec-8389-c4ed68f100da
    `version` INT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 414b8721-afef-498c-a553-5e5b7899599a
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 628cd024-ccaa-4bd6-922c-122a8294f012
    `json_model` STRING NOT NULL COMMENT 'Fineract source column json_model',
    -- column_id: a4e12f0a-c8d8-4306-bfb0-86780a546a06
    `business_date` DATE NOT NULL COMMENT 'Fineract source column business_date',
    -- column_id: 74ff6420-1c3e-4269-a365-9ca808620416
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: aa81d26d-d00b-4ebe-9d05-2dd406c8fe41
    `json_model_version` VARCHAR(100) NOT NULL COMMENT 'Fineract source column json_model_version',
    -- column_id: 003caafa-199e-43a3-8333-59c9ffee9f27
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
