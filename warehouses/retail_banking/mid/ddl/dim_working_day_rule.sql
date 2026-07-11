-- DIM generated from m_working_days
DROP TABLE IF EXISTS retail_banking_dm.dim_working_day_rule;
-- table_id: 6a043ed5-8d66-4833-803d-0e3adf985452
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_working_day_rule (
    -- column_id: e0980f7d-0fbe-4767-b17a-1baaf69c9c68
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5e0b653d-7d81-40a8-9b57-b84b05ec5223
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: df072014-2343-40b0-a1e8-b22b67b2d209
    `repayment_rescheduling_enum` SMALLINT NULL COMMENT 'Fineract source column repayment_rescheduling_enum',
    -- column_id: 34b8f3ae-f673-48f2-9349-9a5181620c23
    `extend_term_daily_repayments` BOOLEAN NULL COMMENT 'Fineract source column extend_term_daily_repayments',
    -- column_id: 47217345-7ef3-426d-a66c-0ede4bfe0529
    `extend_term_holiday_repayment` BOOLEAN NOT NULL COMMENT 'Fineract source column extend_term_holiday_repayment',
    -- column_id: 6af9e62d-4e48-4050-8721-97bccb293a5a
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
