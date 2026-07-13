-- ODS mirror of Apache Fineract m_portfolio_account_associations (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_portfolio_account_associations;
-- table_id: 923474a2-af92-4810-b418-94011017caf3
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_portfolio_account_associations (
    -- column_id: 22a3a7b2-c854-4cb6-8e8a-a3c005cfaaf3
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4a77b2cc-2771-4818-a9e3-346a145ffdb3
    `loan_account_id` BIGINT NULL COMMENT 'Fineract source column loan_account_id',
    -- column_id: ad968aee-2690-4234-9703-2f1a6fddfb06
    `savings_account_id` BIGINT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: fc1a27cd-6fdc-4c0d-a8f9-1aa5e0d2cdc2
    `linked_loan_account_id` BIGINT NULL COMMENT 'Fineract source column linked_loan_account_id',
    -- column_id: 629eaefe-ea75-432c-89b7-3f8cf73e4c6f
    `linked_savings_account_id` BIGINT NULL COMMENT 'Fineract source column linked_savings_account_id',
    -- column_id: af7e440d-debe-4299-9c1d-31dbffd78f7b
    `association_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column association_type_enum',
    -- column_id: d1f65b94-13ec-4782-8cef-f3124bdca926
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 7f89bfb2-bdfa-466a-a2ea-c001fcc07dd2
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
