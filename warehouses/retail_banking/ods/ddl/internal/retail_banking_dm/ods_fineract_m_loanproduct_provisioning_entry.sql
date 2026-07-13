-- ODS mirror of Apache Fineract m_loanproduct_provisioning_entry (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loanproduct_provisioning_entry;
-- table_id: dcdfdf6b-90e7-473b-b41a-53aa194f71a7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loanproduct_provisioning_entry (
    -- column_id: 8688d4c1-9f5f-4cec-a0e6-b34ae06fe4fb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a84dc9d9-155a-4f09-beef-ced6f729e6fc
    `history_id` BIGINT NOT NULL COMMENT 'Fineract source column history_id',
    -- column_id: 69afee04-3184-4a23-bd6b-64a9df91ca94
    `criteria_id` BIGINT NOT NULL COMMENT 'Fineract source column criteria_id',
    -- column_id: 244d8a4a-d833-4583-8801-39384dcfaabb
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: a213974d-bd44-4216-b56a-6ad53bc6f80b
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: f0412311-4dda-4c57-8329-b69011eca667
    `product_id` BIGINT NOT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 1e0d52b3-e76d-4233-bc00-7c2eff650f86
    `category_id` BIGINT NOT NULL COMMENT 'Fineract source column category_id',
    -- column_id: 1639845b-5afc-4df4-bf69-a5d553a54464
    `overdue_in_days` BIGINT NULL COMMENT 'Fineract source column overdue_in_days',
    -- column_id: 710fbdb8-8e2a-434a-bc84-c4d3a398ee25
    `reseve_amount` DECIMAL(20,6) NULL COMMENT 'Fineract source column reseve_amount',
    -- column_id: 5fe30229-733a-4b60-a794-3ea9c13a1ee4
    `liability_account` BIGINT NULL COMMENT 'Fineract source column liability_account',
    -- column_id: 003327d1-cd1c-45be-a012-807fab7fe6b4
    `expense_account` BIGINT NULL COMMENT 'Fineract source column expense_account',
    -- column_id: 405108fd-5723-457f-8c93-41fa10135a1d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
