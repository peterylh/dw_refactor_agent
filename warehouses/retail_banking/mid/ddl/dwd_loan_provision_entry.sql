-- DWD generated from m_loanproduct_provisioning_entry
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_provision_entry;
-- table_id: bca9a4c0-4bad-4f20-89f1-48d1999c06c3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_provision_entry (
    -- column_id: ff1bd84f-8336-4af6-92fe-f1541dd45d45
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 27de3514-efe1-4e14-8827-2b7c4d352b0b
    `history_id` BIGINT NOT NULL COMMENT 'Fineract source column history_id',
    -- column_id: b1b3f1a7-d803-4c4b-87fe-db8fba608632
    `criteria_id` BIGINT NOT NULL COMMENT 'Fineract source column criteria_id',
    -- column_id: 97f2270d-38cd-4e02-971a-db612326bced
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 9a3fb917-1f7e-44ec-9363-cca03beb5367
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 84531f26-cfc5-4177-a586-1137b18ee9da
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: afad2bd7-49ef-482a-b6e2-3c540060805b
    `category_id` BIGINT NOT NULL COMMENT 'Fineract source column category_id',
    -- column_id: 77bdb8dd-b4a2-49cd-b097-b8f435310d44
    `overdue_in_days` BIGINT NULL COMMENT 'Fineract source column overdue_in_days',
    -- column_id: 4e0e6ea5-cf6f-4a31-ad6a-5e8f4f6e0090
    `reseve_amount` DECIMAL(20,6) NULL COMMENT 'Fineract source column reseve_amount',
    -- column_id: fe85dba4-16a8-4916-8e27-8e3475fb4a03
    `liability_account` BIGINT NULL COMMENT 'Fineract source column liability_account',
    -- column_id: 3f8b58a4-1fea-4361-8106-21943859d97c
    `expense_account` BIGINT NULL COMMENT 'Fineract source column expense_account',
    -- column_id: c8963629-f80e-412c-930d-7b502f55041d
    `provision_date` DATE NULL COMMENT 'Provisioning run business date',
    -- column_id: 142e2876-3520-458b-bbbc-223b322d886e
    `journal_entry_created` BOOLEAN NULL COMMENT 'Whether the provisioning run posted journal entries',
    -- column_id: a83149e6-ed4d-4f20-9c75-0b3894c5fa36
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
