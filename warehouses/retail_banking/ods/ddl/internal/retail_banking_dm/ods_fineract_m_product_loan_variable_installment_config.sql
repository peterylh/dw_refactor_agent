-- ODS mirror of Apache Fineract m_product_loan_variable_installment_config (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_product_loan_variable_installment_config;
-- table_id: 127f9951-409f-48be-958b-a8978b49aa4b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_product_loan_variable_installment_config (
    -- column_id: f2ff871d-51ec-4328-b124-f1fcb0a679ae
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: feace056-c7e1-4d1c-b005-2caf79fb6fc2
    `loan_product_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_product_id',
    -- column_id: f9235d71-f92d-4aa2-9f9b-84406d6d81c0
    `minimum_gap` INT NOT NULL COMMENT 'Fineract source column minimum_gap',
    -- column_id: 680d5701-a26e-483e-84d5-c02a52e2df17
    `maximum_gap` INT NOT NULL COMMENT 'Fineract source column maximum_gap',
    -- column_id: 14d7fa54-0e22-4766-bf80-d148789d0d1b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
