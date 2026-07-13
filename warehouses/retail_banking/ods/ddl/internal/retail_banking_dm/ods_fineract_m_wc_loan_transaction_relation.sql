-- ODS mirror of Apache Fineract m_wc_loan_transaction_relation (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction_relation;
-- table_id: b8b1531b-e880-4bf3-8c9a-b0a23cec6d26
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_transaction_relation (
    -- column_id: 9ce00f3a-f52b-4ce2-a636-e4f8679eb1cc
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a14c73e4-9243-419d-83d4-9079fc8e89ea
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: ea0bd6a7-a886-475d-a1af-2c7e38416e86
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 9e860ddc-cc2c-4540-8ded-7a04cf074405
    `from_loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column from_loan_transaction_id',
    -- column_id: 8695ae91-25a1-45dd-8585-4b10e0742925
    `to_loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column to_loan_transaction_id',
    -- column_id: 738ea365-45eb-4804-bb20-8992eb0bcb89
    `relation_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column relation_type_enum',
    -- column_id: 45264a92-6d13-4bae-82ec-4e9133d9f9da
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 5e436c67-f200-4478-867e-1557e832d9b8
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 6f96b284-eabb-41d0-a35a-2c032ff18b5c
    `to_loan_charge_id` BIGINT NULL COMMENT 'Fineract source column to_loan_charge_id',
    -- column_id: 03a4ea7a-ef5a-425e-a629-e172e1cd4c97
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
