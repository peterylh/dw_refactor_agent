-- ODS mirror of Apache Fineract m_client_address (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_address;
-- table_id: 2adaadc8-0adf-4f1b-a280-abf980a59137
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_address (
    -- column_id: 0615c7f0-1bb1-4142-9530-f66b4435bf9b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 586173e0-8169-4b4f-89a7-7f51a5154411
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 1eae5780-b797-4a15-bca2-b265195159c2
    `address_id` BIGINT NOT NULL COMMENT 'Fineract source column address_id',
    -- column_id: d452ea8c-6931-4af8-aace-e0f2397dff09
    `address_type_id` INT NOT NULL COMMENT 'Fineract source column address_type_id',
    -- column_id: cff3cc9c-511d-4c47-b31a-2fa429c91e08
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 44f8941c-2ac6-4961-af17-497ce28c1602
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
