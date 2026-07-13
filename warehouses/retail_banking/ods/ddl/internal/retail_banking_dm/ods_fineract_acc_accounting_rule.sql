-- ODS mirror of Apache Fineract acc_accounting_rule (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_accounting_rule;
-- table_id: 70754f0b-0a01-475b-b70c-baac68835dc9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_accounting_rule (
    -- column_id: ccc05735-34e7-41cc-82e8-338ab7d434c9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 73d02825-7601-48b7-a36c-2abd37513997
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: 888e2c3c-7be2-444f-890c-1d2e6e0fbc74
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 6484248e-aba8-4298-b1c1-6e35a01e4f66
    `debit_account_id` BIGINT NULL COMMENT 'Fineract source column debit_account_id',
    -- column_id: 40ae2582-d47c-441e-81ce-9b10dbc0f59d
    `allow_multiple_debits` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_debits',
    -- column_id: b2e0abad-9648-4b62-8e29-c2464d42983e
    `credit_account_id` BIGINT NULL COMMENT 'Fineract source column credit_account_id',
    -- column_id: 4514a697-c40d-4c93-aa20-45ebc60459e9
    `allow_multiple_credits` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_multiple_credits',
    -- column_id: cbc030c7-4087-44b6-a7a7-28047ec81e75
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 0b5cbfae-934b-45bf-92b8-36a31b5e9d94
    `system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column system_defined',
    -- column_id: e4c46e61-2e48-4baa-959a-74ff68f3326d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
