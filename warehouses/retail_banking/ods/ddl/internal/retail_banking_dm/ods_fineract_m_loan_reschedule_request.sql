-- ODS mirror of Apache Fineract m_loan_reschedule_request (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_reschedule_request;
-- table_id: 89c5e67e-1fca-4157-9aa3-6028d5708afa
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_reschedule_request (
    -- column_id: 74a47b19-ec3a-4d8f-b894-889df4e87887
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cc66e01e-f8ac-4eb1-9f9e-329657174724
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: cdf1aa85-90df-4697-9265-67c425f5bb84
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 1dd78b05-e996-4ac1-bca2-6002d8dc2798
    `reschedule_from_installment` SMALLINT NOT NULL COMMENT 'Rescheduling will start from this installment',
    -- column_id: 92a7cb8b-5763-48a8-aeff-a0aab587206e
    `reschedule_from_date` DATE NOT NULL COMMENT 'Rescheduling will start from the installment with due date similar to this date.',
    -- column_id: 46cb498d-3f22-4d88-b8fe-94dc92ffa452
    `recalculate_interest` BOOLEAN NULL COMMENT 'If set to 1, interest will be recalculated starting from the reschedule period.',
    -- column_id: c8ee9625-0641-4231-be64-78f194365197
    `reschedule_reason_cv_id` INT NULL COMMENT 'ID of code value of reason for rescheduling',
    -- column_id: 8ec88285-6dc4-4eee-b741-3265e9603273
    `reschedule_reason_comment` VARCHAR(500) NULL COMMENT 'Text provided in addition to the reason code value',
    -- column_id: 6cf5082c-47b5-4e03-ae48-7bfb76a59ba4
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: f6b9cb75-b2ca-43a5-ab8e-0d97d9a6477a
    `submitted_by_user_id` BIGINT NOT NULL COMMENT 'Fineract source column submitted_by_user_id',
    -- column_id: 74b8887a-f002-456d-9237-2a0634b283c8
    `approved_on_date` DATE NULL COMMENT 'Fineract source column approved_on_date',
    -- column_id: cbb36289-fe34-4755-bd95-7b818d6b4a77
    `approved_by_user_id` BIGINT NULL COMMENT 'Fineract source column approved_by_user_id',
    -- column_id: f1576b22-8f44-4c66-a8be-4d3d7428287c
    `rejected_on_date` DATE NULL COMMENT 'Fineract source column rejected_on_date',
    -- column_id: 2b0360ec-66dd-4f25-9500-d8e8df363c6d
    `rejected_by_user_id` BIGINT NULL COMMENT 'Fineract source column rejected_by_user_id',
    -- column_id: 1f3b0d0c-3cca-4cae-b184-6b6c850d68b8
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
