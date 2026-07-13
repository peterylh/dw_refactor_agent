-- ODS mirror of Apache Fineract m_loan_overdue_installment_charge (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_overdue_installment_charge;
-- table_id: 23928c0a-29be-472a-97b7-eef708169ed9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_overdue_installment_charge (
    -- column_id: 2cba12c6-818c-4e79-b6c6-6f78ffbfeb94
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1c81bf8c-eb64-4ef6-981c-5f220b0088da
    `loan_charge_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_charge_id',
    -- column_id: 610e8ba2-61be-4846-a2a2-799b75b40adb
    `loan_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_schedule_id',
    -- column_id: 80068337-2688-4aa7-8f1d-d60cfa9c8b08
    `frequency_number` INT NOT NULL COMMENT 'Fineract source column frequency_number',
    -- column_id: 9c3a43ba-c49c-44a1-80b4-f66094f6d613
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
