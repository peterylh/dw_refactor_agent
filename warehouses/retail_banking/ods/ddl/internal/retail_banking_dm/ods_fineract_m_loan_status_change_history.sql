-- ODS mirror of Apache Fineract m_loan_status_change_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_status_change_history;
-- table_id: ac9b42f7-4d2e-460c-ad46-c381abf94e5d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_status_change_history (
    -- column_id: 5b8b3e31-0063-41f4-9043-965cfdcdc656
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 33c8bef4-86a9-460b-88fd-db7f755793bb
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 5737ceeb-c3b5-470f-99c0-5820336d50ce
    `status_code` VARCHAR(255) NOT NULL COMMENT 'Fineract source column status_code',
    -- column_id: 8b3c8d72-1bf0-4ee3-ab64-fcc5c78e991c
    `status_change_business_date` DATE NOT NULL COMMENT 'Fineract source column status_change_business_date',
    -- column_id: 6755c602-cbde-4755-ade0-6402eb9e291c
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 9a8b5ca6-4ccd-49fd-8adc-100c85385632
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: ed9fc332-7d73-4a0f-b801-37fc7a560dda
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 8afef1f1-4757-48cf-8885-79d1bbcb4940
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 2519e3f8-7935-4f0d-a592-df320cae99b4
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
