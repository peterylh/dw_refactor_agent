-- ODS mirror of Apache Fineract m_floating_rates_periods (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_floating_rates_periods;
-- table_id: d74e893f-7ae5-4bc0-8eb5-b6b7a0ef5c9e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_floating_rates_periods (
    -- column_id: 38fab045-d903-418b-a999-0668efab1c6f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 509be613-1cda-4705-914c-cf0ffa48099a
    `floating_rates_id` BIGINT NOT NULL COMMENT 'Fineract source column floating_rates_id',
    -- column_id: 1698f821-dcd2-4241-bd85-dbb03022eeb5
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: bfb0b15d-4d78-4013-b5e8-34e863273b3f
    `interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_rate',
    -- column_id: c295cd09-0b28-4e60-9a11-2d83d34a6c3a
    `is_differential_to_base_lending_rate` BOOLEAN NOT NULL COMMENT 'Fineract source column is_differential_to_base_lending_rate',
    -- column_id: 28b4ea4b-f541-41f4-8387-7142316d5802
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 88f3a186-2d98-4305-aa8f-c80efbdc9eda
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 45d7dadc-a045-4c91-9153-0fc0172d986e
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 656b0ddd-52ce-4131-9eb1-dada2d811d9b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: bd7f3a15-4351-4e67-8216-a0288f1b3ff2
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 89f34c27-8a76-439a-90ca-faf653b49d25
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 93e8c0c3-316d-45ba-9235-982cc648c599
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 1fb0347b-5d15-47e6-a0f6-e3945d0de232
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
