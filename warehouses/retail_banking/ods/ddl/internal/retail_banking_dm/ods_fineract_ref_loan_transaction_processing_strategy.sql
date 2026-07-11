-- ODS mirror of Apache Fineract ref_loan_transaction_processing_strategy (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_ref_loan_transaction_processing_strategy;
-- table_id: dbae9f77-555b-4ade-9e22-9b045a883947
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_ref_loan_transaction_processing_strategy (
    -- column_id: 5b4b9dea-55f0-448b-9e5e-399e8b284f12
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 93fd7f3a-fd64-47ca-bbed-2ae3f573c3d4
    `code` VARCHAR(100) NULL COMMENT 'Fineract source column code',
    -- column_id: fb7c82eb-a2ac-4d99-bdc3-9f6b964d549f
    `name` VARCHAR(255) NULL COMMENT 'Fineract source column name',
    -- column_id: 81d3cf73-5623-4a8b-af22-a9dad14e25ad
    `sort_order` INT NULL COMMENT 'Fineract source column sort_order',
    -- column_id: e16bac0b-d037-405e-ab45-111a7323d100
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
