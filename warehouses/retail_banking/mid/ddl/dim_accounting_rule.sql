-- DIM generated from acc_accounting_rule
DROP TABLE IF EXISTS retail_banking_dm.dim_accounting_rule;
-- table_id: 52382166-c89d-43a0-a738-4fcf3fcdb51e
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_accounting_rule (
    -- column_id: 33509d04-87ed-4a53-abd5-82148f11d802
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 928f694a-5424-4ce1-9eab-7904fbd95cbb
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 4b33f20f-3402-4d2f-a173-ad632b4b2f69
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 13c9121c-dae4-4026-b0e5-a61d645f66d8
    `debit_account_id` BIGINT NULL COMMENT 'Fineract source column debit_account_id',
    -- column_id: 7fb2edb0-40cc-414b-843f-b5aad0a24fc2
    `allow_multiple_debits` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_debits',
    -- column_id: 20522bcc-e2f9-433e-91d8-5b1ef5c04363
    `credit_account_id` BIGINT NULL COMMENT 'Fineract source column credit_account_id',
    -- column_id: 35902f78-abc5-4a5b-9792-92fd97fe1e5b
    `allow_multiple_credits` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_credits',
    -- column_id: f753219e-23a7-48e9-8542-03dde293c7d3
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 4110eb29-ccc4-48bc-9783-f29d569f6fea
    `system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column system_defined',
    -- column_id: 8018327a-502b-4d98-871c-3d96c87a8194
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
