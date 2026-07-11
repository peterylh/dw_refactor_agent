-- ODS mirror of Apache Fineract m_product_loan_guarantee_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_guarantee_details;
-- table_id: 68757933-a20d-484e-8cb0-3d50811078f7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_guarantee_details (
    -- column_id: 113decfc-4054-4371-993d-749b4979722e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 30ba73d8-f720-45e7-812b-c96031128d45
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: c7b44c45-84d4-4a70-ab50-24085a67bfd4
    `mandatory_guarantee` DECIMAL(19,5) NOT NULL COMMENT 'Fineract source column mandatory_guarantee',
    -- column_id: 7edd9947-ecda-483c-9ef1-c59c5e0606b9
    `minimum_guarantee_from_own_funds` DECIMAL(19,5) NULL COMMENT 'Fineract source column minimum_guarantee_from_own_funds',
    -- column_id: f4fc3f92-9df6-463d-b7eb-be509f6a64d1
    `minimum_guarantee_from_guarantor_funds` DECIMAL(19,5) NULL COMMENT 'Fineract source column minimum_guarantee_from_guarantor_funds',
    -- column_id: ea0f27bd-6f84-4ba1-a74c-ecbabdba4f11
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
