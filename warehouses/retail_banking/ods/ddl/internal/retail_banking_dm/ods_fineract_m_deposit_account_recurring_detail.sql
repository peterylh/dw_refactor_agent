-- ODS mirror of Apache Fineract m_deposit_account_recurring_detail (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_account_recurring_detail;
-- table_id: 37eead6f-ec0b-4409-8e00-fa2999aae40f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_account_recurring_detail (
    -- column_id: eb84ee1e-2d78-40c2-9c39-7aa4c15245c9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f3fc3f10-66b1-4f03-be44-6308672dc8c9
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: ca75ff34-43fe-4db0-a006-f64a0cfa82d6
    `mandatory_recommended_deposit_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column mandatory_recommended_deposit_amount',
    -- column_id: 24db8b9c-bfe7-4154-b3b2-bb651e9dc7ea
    `is_mandatory` BOOLEAN NOT NULL COMMENT 'Fineract source column is_mandatory',
    -- column_id: b0e5eafa-5f7e-4931-ba32-053040b6676d
    `allow_withdrawal` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_withdrawal',
    -- column_id: 77e46072-e5cc-465e-b0dc-dc9ba382df21
    `adjust_advance_towards_future_payments` BOOLEAN NOT NULL COMMENT 'Fineract source column adjust_advance_towards_future_payments',
    -- column_id: 4986db01-b3f9-4364-bf31-aa6da7bc69be
    `is_calendar_inherited` BOOLEAN NOT NULL COMMENT 'Fineract source column is_calendar_inherited',
    -- column_id: 5fd56059-fb92-433d-80fe-2914ec27b3e8
    `total_overdue_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column total_overdue_amount',
    -- column_id: a9890d31-eae3-4be7-b490-027469536afe
    `no_of_overdue_installments` INT NULL COMMENT 'Fineract source column no_of_overdue_installments',
    -- column_id: 89d4aa3f-2fa8-4789-9f38-0fe4395dbd5d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
