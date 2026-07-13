-- ODS mirror of Apache Fineract m_creditbureau_loanproduct_mapping (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_creditbureau_loanproduct_mapping;
-- table_id: 80fa079a-4374-4665-90cc-753320f7ade4
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_creditbureau_loanproduct_mapping (
    -- column_id: f21c52fc-c237-417a-839d-c4e288715e96
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5cc06256-16e7-4b68-8edf-9af24333dcdc
    `organisation_creditbureau_id` BIGINT NOT NULL COMMENT 'Fineract source column organisation_creditbureau_id',
    -- column_id: 1b4e5244-989f-4c7f-b6bf-8aa39b0995d7
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: 95c057a9-5a94-4cf0-9123-810e2fa384ad
    `is_creditcheck_mandatory` BOOLEAN NULL COMMENT 'Fineract source column is_creditcheck_mandatory',
    -- column_id: 3681a1d0-8d70-4de7-a73b-c71612b9c106
    `skip_creditcheck_in_failure` BOOLEAN NULL COMMENT 'Fineract source column skip_creditcheck_in_failure',
    -- column_id: 576123aa-41e5-4875-8cab-24c9cd80d083
    `stale_period` INT NULL COMMENT 'Fineract source column stale_period',
    -- column_id: bc779958-1862-4139-af30-7e6b1df9cb39
    `is_active` BOOLEAN NULL COMMENT 'Fineract source column is_active',
    -- column_id: e577f0a7-ffac-4176-a341-dbb07b7ccf21
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
