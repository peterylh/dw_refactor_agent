-- ODS mirror of Apache Fineract m_savings_account_interest_rate_slab (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_interest_rate_slab;
-- table_id: 284cc132-ea38-4d6f-99ce-3c84c5b1c83b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_interest_rate_slab (
    -- column_id: c24ba65c-cef9-4f24-948b-c87ac133712a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c319bae6-4283-4c99-b1e9-0abc70d0e3f7
    `savings_account_interest_rate_chart_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_interest_rate_chart_id',
    -- column_id: c1ecb92f-334c-4756-b476-c6aa95b83098
    `description` VARCHAR(200) NULL COMMENT 'Fineract source column description',
    -- column_id: 8e945921-ca3c-46ba-84b8-b4ec50b21b60
    `period_type_enum` SMALLINT NULL COMMENT 'Fineract source column period_type_enum',
    -- column_id: f47124c7-7cfa-4e1c-9145-b3811de272a9
    `from_period` INT NULL COMMENT 'Fineract source column from_period',
    -- column_id: cec5e2c8-01b5-4925-8a87-33e2b6b9b4d0
    `to_period` INT NULL COMMENT 'Fineract source column to_period',
    -- column_id: efbd9a1c-4a3f-4622-b731-5a4c7b566224
    `amount_range_from` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_range_from',
    -- column_id: 08cb18d2-c099-43a4-95ff-d80af2cccf63
    `amount_range_to` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_range_to',
    -- column_id: 55a52e53-875b-448d-b5c4-7dd69779f92e
    `annual_interest_rate` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column annual_interest_rate',
    -- column_id: 492040b0-b60f-433c-9447-bb0ea3e01e43
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 86b94597-e7f4-420c-b642-56c46f0b2c37
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
