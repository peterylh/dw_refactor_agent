-- ODS mirror of Apache Fineract acc_gl_journal_entry_annual_summary (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_gl_journal_entry_annual_summary;
-- table_id: 8fb681ef-c572-476d-8294-04cf92af304f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_gl_journal_entry_annual_summary (
    -- column_id: 3a372811-c682-400e-9f6c-3f98fea446bd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bea6654a-bed4-4e02-8352-bdd6e3f301a6
    `gl_code` VARCHAR(45) NOT NULL COMMENT 'Fineract source column gl_code',
    -- column_id: 49014023-db2c-4b69-a627-cba6d122d126
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: cbbf16a1-531e-440f-9938-baa49cfc0269
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 38a50355-8ae9-4ea3-ba7d-b33226521f73
    `opening_balance_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column opening_balance_amount',
    -- column_id: 8f2defe5-cdaf-410c-99e1-eec732cafdd2
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: c2f671f5-77cd-4a4a-83ea-ed2e90544f95
    `owner_external_id` VARCHAR(100) NULL COMMENT 'Fineract source column owner_external_id',
    -- column_id: 112491a1-497b-4980-8845-e76f4dd9e0ab
    `manual_entry` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_entry',
    -- column_id: 7382adf1-2301-487b-b782-305d795be7aa
    `year_end_date` DATE NOT NULL COMMENT 'Fineract source column year_end_date',
    -- column_id: c1a80b15-b02a-40a2-8b7a-cae0800e0ccf
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 8df27c13-e3f9-412d-99cc-fec4211b6493
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 77f8c1f4-ac55-4333-9244-3d12467e6d21
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: f82c88bd-a852-4296-badd-cd5408b1ab52
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 162e0f00-8e03-47c8-8c99-d3159e130b22
    `originator_external_ids` VARCHAR(1000) NULL COMMENT 'Fineract source column originator_external_ids',
    -- column_id: 8ef990dc-c0bd-42b9-88d8-4bb0a69b900b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
