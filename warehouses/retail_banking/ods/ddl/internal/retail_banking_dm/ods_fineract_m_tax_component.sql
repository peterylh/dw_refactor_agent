-- ODS mirror of Apache Fineract m_tax_component (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_tax_component;
-- table_id: 05c69c5d-e236-48cf-9100-174cbf16846d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_tax_component (
    -- column_id: cc0b0900-0643-4e47-ab39-369b070fe31e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7d09e815-f6d6-4593-9211-c53b20e7b41a
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 2eb6cb6f-322b-4805-8b30-13544ed92cda
    `percentage` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column percentage',
    -- column_id: eb3fa336-24df-472b-8e04-7cfa6ebd5b6a
    `debit_account_type_enum` SMALLINT NULL COMMENT 'Fineract source column debit_account_type_enum',
    -- column_id: 55c2adab-dd66-484f-a610-507aa8badc2f
    `debit_account_id` BIGINT NULL COMMENT 'Fineract source column debit_account_id',
    -- column_id: ebbb74dd-c55a-4e8b-8a20-b595d41d4ad3
    `credit_account_type_enum` SMALLINT NULL COMMENT 'Fineract source column credit_account_type_enum',
    -- column_id: 25853071-86dc-4a92-8c34-98ffa9e04b3c
    `credit_account_id` BIGINT NULL COMMENT 'Fineract source column credit_account_id',
    -- column_id: 812eb5b1-94f4-4695-84fb-d9afecc28ce4
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 73f5bff9-8acd-40ad-a626-f55f07e561e8
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 6a872655-2783-4901-8ec9-2e9decc193a9
    `created_date` DATETIME NOT NULL COMMENT 'Fineract source column created_date',
    -- column_id: cdf49d11-a7f2-4714-aabe-fccf22bb6079
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 3864aa25-2fd4-4db6-9f2d-2d00c8b11b35
    `lastmodified_date` DATETIME NOT NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 1ad071ef-f757-4536-b218-567d67ffe061
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
