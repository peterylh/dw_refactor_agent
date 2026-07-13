-- ODS mirror of Apache Fineract m_loan_charge_paid_by (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_charge_paid_by;
-- table_id: 53d64138-4251-407c-b41e-30bf0aa6d642
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_charge_paid_by (
    -- column_id: ec01fce1-dc9e-41b2-849c-32f9d0ddf841
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 8450b531-6bcb-4153-9325-db1faeb8c0dc
    `loan_transaction_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_transaction_id',
    -- column_id: 0aa8b9c0-e65d-432a-96e6-75f32132a44b
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 5faea5e3-9e7b-4bf3-83b0-c99f6305fa90
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 1b5d1022-9566-4d68-b469-d78a796f9471
    `installment_number` SMALLINT NULL COMMENT 'Fineract source column installment_number',
    -- column_id: c79b63be-de64-4b0a-b1b4-848419cda3f5
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
