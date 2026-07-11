-- ODS mirror of Apache Fineract m_loan_installment_charge (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_installment_charge;
-- table_id: 4004b5a7-c338-4339-9336-c6cb0203776e
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_installment_charge (
    -- column_id: 80133112-52f5-43f8-986b-9cd0df0f1d4e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d13bee69-b71e-4d0e-950b-40407f58f182
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 79ce1845-3304-414d-8e65-478f6bc3b4ec
    `loan_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_schedule_id',
    -- column_id: 6a695508-5c88-4c3b-a111-fb46e2c47ca9
    `due_date` DATE NULL COMMENT 'Fineract source column due_date',
    -- column_id: a6ffdef3-6748-4c7e-b2a4-173eeb830d88
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: e2d99c98-9433-4a25-854a-b5d8271e0996
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: b37e498f-62ba-4039-9d7c-8f0c704d19cf
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: a9820c40-2db7-4a05-9bf5-87217db861a2
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 5534a91d-26a6-46dc-ad6c-a2b1526c202a
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: 7b331443-c7ec-4979-9830-8058e686762d
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 2d890d43-0b95-40f8-b835-54f9b8e9f7f3
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: 95873352-a3ac-4286-859c-0b6931f7a869
    `amount_through_charge_payment` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_through_charge_payment',
    -- column_id: 929ff8f2-f09d-4610-b543-05c6dbc8cdcf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
