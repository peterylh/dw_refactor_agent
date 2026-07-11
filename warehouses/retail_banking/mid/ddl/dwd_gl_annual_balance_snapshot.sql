-- DWD generated from acc_gl_journal_entry_annual_summary
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_annual_balance_snapshot;
-- table_id: 028d026f-17c5-4cc3-b031-2a7e0f2b5c54
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_annual_balance_snapshot (
    -- column_id: 8e01eff7-2bd6-4381-b386-56a2b1394783
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a6417e8a-103e-4102-8c3f-c60b9297e522
    `gl_code` VARCHAR(45) NOT NULL COMMENT 'Fineract source column gl_code',
    -- column_id: 5e4885b2-a16b-45be-9c83-a365c956dba5
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 2cfb676c-c5ac-46b6-a3a7-63bb6ce19b36
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 8444ac87-35ea-4108-ac5a-7d1ec3b5dfc0
    `opening_balance_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column opening_balance_amount',
    -- column_id: e01747f3-2ecd-4832-9225-ed6fe80268a5
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 8f778a58-963b-4ac8-98e1-9f61f8bf8614
    `owner_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column owner_external_id',
    -- column_id: fb80c604-6ea0-401b-81ca-8b6587817274
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: 8648e5bf-c0fc-49a9-b107-e6b152bcf9f4
    `year_end_date` DATE NOT NULL COMMENT 'Fineract source column year_end_date',
    -- column_id: 2573f072-3a3c-4da2-85c5-6c33e5d42750
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e2bbd310-2b0b-45a4-bf37-40effe8385aa
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 20ebf1c6-c828-4772-bf3f-e9362f89d2f0
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: eb352bd3-b754-427e-8e8e-ff29b27dcc64
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: edb7945b-cb43-4615-bda4-d3bc9eadeac0
    `originator_external_ids` VARCHAR(1000) NULL COMMENT 'Fineract source column originator_external_ids',
    -- column_id: c000f0bd-2c5d-4051-95bb-d1650a6266dc
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 461adfde-ba14-4db6-ad37-ecf175f03fb8
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
