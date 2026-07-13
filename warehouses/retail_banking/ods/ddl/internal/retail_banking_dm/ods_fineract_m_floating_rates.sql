-- ODS mirror of Apache Fineract m_floating_rates (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_floating_rates;
-- table_id: be698106-e9e6-4bf8-af81-a6884a040441
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_floating_rates (
    -- column_id: 1bcfea80-0132-4101-9db4-87afdb870235
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2bcd4da3-841f-444c-90e8-849b66097048
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 54628123-e08c-4b25-99d5-e6f25c34afeb
    `is_base_lending_rate` BOOLEAN NOT NULL COMMENT 'Fineract source column is_base_lending_rate',
    -- column_id: 90c66426-0c09-4c4d-a57c-660465c37659
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 56973b88-7b4c-4b83-8bb2-f6377b9e30d7
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1006c281-2be9-41e5-b8c0-5a59cdffdc3b
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 39eaf780-de25-4619-a1ae-7c598fdc0458
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 1b4d5f76-e6f3-4270-ab00-8652520b05a8
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 6cfeab62-1ede-4cba-b84b-a9b5e8aa8785
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: a71f3567-1bd7-4a93-a67e-6d41d9f9e829
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: b6ba8eda-9686-4774-8b24-b303c30ceaec
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
