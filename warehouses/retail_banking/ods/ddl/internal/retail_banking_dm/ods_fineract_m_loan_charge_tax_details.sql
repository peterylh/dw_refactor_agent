-- ODS mirror of Apache Fineract m_loan_charge_tax_details (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_charge_tax_details;
-- table_id: f677883e-bb4c-4787-8875-de7cca0cac46
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_charge_tax_details (
    -- column_id: ae26d385-a862-4344-b7a4-0131452e20d0
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ce77119c-5bd7-4b30-a29b-8f2f62d18129
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 18df22e1-333a-47c7-b3ae-1bf08ecc849b
    `tax_component_id` BIGINT NOT NULL COMMENT 'Fineract source column tax_component_id',
    -- column_id: 4de8e2c3-fe15-4648-bbd0-eb952a14478a
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: a9fa3468-02d1-48ad-b7d9-432c9b0ce3ca
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
