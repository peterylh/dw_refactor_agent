-- ODS mirror of Apache Fineract m_repayment_with_post_dated_checks (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_repayment_with_post_dated_checks;
-- table_id: 3fa8ff86-2993-4447-a8c7-621edde803ec
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_repayment_with_post_dated_checks (
    -- column_id: d5747308-8064-4393-9f36-f8adf82916f9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 2a23dcd4-fcda-4a17-ae67-35ec180c1ed6
    `check_no` BIGINT NOT NULL COMMENT 'Fineract source column check_no',
    -- column_id: 09405770-3d67-4426-96af-f8c310a84c3f
    `amount` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: eb5116e6-45af-4273-9b27-6fb28adcb9ad
    `loan_id` BIGINT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: ad9c8573-d5a4-469f-be17-bee85fb3883b
    `repayment_id` BIGINT NULL COMMENT 'Fineract source column repayment_id',
    -- column_id: 00fddf43-28f4-4aa4-9c6b-869fe8d1cd58
    `account_no` BIGINT NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 1911329a-4fab-47f9-b878-7960bd2ab90a
    `bank_name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column bank_name',
    -- column_id: 9f00c545-74fe-4630-8e81-73d4b5297a35
    `repayment_date` DATE NOT NULL COMMENT 'Fineract source column repayment_date',
    -- column_id: 5924a63d-50d5-4a86-bb7a-e2e685c1d056
    `status` SMALLINT NULL COMMENT 'Fineract source column status',
    -- column_id: 5c530028-a148-449a-9265-107c04679ac0
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
