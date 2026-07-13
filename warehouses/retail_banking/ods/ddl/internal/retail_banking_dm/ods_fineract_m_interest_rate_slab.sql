-- ODS mirror of Apache Fineract m_interest_rate_slab (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_interest_rate_slab;
-- table_id: 55a79259-68c2-476b-ae3f-39717977e6f7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_interest_rate_slab (
    -- column_id: b9d34582-83ff-4498-ba5d-76c34b927584
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 118614b5-c2e0-49d4-acd4-97cce5fa7408
    `interest_rate_chart_id` BIGINT NOT NULL COMMENT 'Fineract source column interest_rate_chart_id',
    -- column_id: cc73573d-34ff-4171-a182-c9f50f999394
    `description` VARCHAR(200) NULL COMMENT 'Fineract source column description',
    -- column_id: 6d75bd7f-0a1b-4526-aa96-7584be513367
    `period_type_enum` SMALLINT NULL COMMENT 'Fineract source column period_type_enum',
    -- column_id: 9d6e66d0-3d62-412e-8357-13dbfa8565cf
    `from_period` INT NULL COMMENT 'Fineract source column from_period',
    -- column_id: c285b893-e82a-4480-9187-e6e8152944b2
    `to_period` INT NULL COMMENT 'Fineract source column to_period',
    -- column_id: 5ea40288-d5ea-4f89-a85c-ccf6faf01c0f
    `amount_range_from` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_range_from',
    -- column_id: 3628813b-9d9b-40f9-93f5-8d0d0acdb615
    `amount_range_to` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_range_to',
    -- column_id: e3e1fb9b-83f2-44ab-810b-d0682f767cf2
    `annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column annual_interest_rate',
    -- column_id: 365b50a3-f6c6-490f-ba6e-aba860e0be71
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 760fa342-040c-4d64-ac75-7736dd5c3061
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
