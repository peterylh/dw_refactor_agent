-- ODS mirror of Apache Fineract m_guarantor_transaction (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_guarantor_transaction;
-- table_id: 9c76800a-5603-44aa-ab64-e840c0a612dd
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_guarantor_transaction (
    -- column_id: d15e2fcd-119a-40a5-a605-43e8132fd1a6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7c311c6e-dc1f-40a4-ae33-13b40a3730be
    `guarantor_fund_detail_id` BIGINT NOT NULL COMMENT 'Fineract source column guarantor_fund_detail_id',
    -- column_id: fc4e0537-5520-424f-bf72-7c25aa727184
    `loan_transaction_id` BIGINT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 3ccd6f92-d262-41a6-b5c0-6050af5755be
    `deposit_on_hold_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column deposit_on_hold_transaction_id',
    -- column_id: b1bc6c04-88ac-4c6a-aa27-50ae4227091b
    `is_reversed` BOOLEAN NOT NULL COMMENT 'Fineract source column is_reversed',
    -- column_id: 80fedf98-2db6-40f3-84b8-1fff55b0e5e1
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
