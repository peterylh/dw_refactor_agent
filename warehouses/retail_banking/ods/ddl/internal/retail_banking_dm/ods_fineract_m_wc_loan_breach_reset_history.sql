-- ODS mirror of Apache Fineract m_wc_loan_breach_reset_history (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_reset_history;
-- table_id: 479a4a03-b2ee-493e-ad31-3e0b26b6c28b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_breach_reset_history (
    -- column_id: 1c0e344f-3180-4e6d-b48e-38daf0f320b4
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f0e20582-86bd-447c-b5ed-d04243b2bd13
    `breach_action_id` BIGINT NOT NULL COMMENT 'Fineract source column breach_action_id',
    -- column_id: 63e9a2cc-fbd4-45e2-a3e4-cb5b91956331
    `breach_schedule_id` BIGINT NOT NULL COMMENT 'Fineract source column breach_schedule_id',
    -- column_id: cec92d7c-b18f-411d-a88c-81b2fa9143ae
    `outstanding_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_amount',
    -- column_id: 5e8a9c7d-4606-42c5-af33-e1459609f556
    `breach` BOOLEAN NULL COMMENT 'Fineract source column breach',
    -- column_id: 2ed8c707-61cc-40c7-a982-081b9c122008
    `near_breach` BOOLEAN NULL COMMENT 'Fineract source column near_breach',
    -- column_id: 25bfc272-05d4-4898-9133-30e7785f2b12
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 65504c75-e9d4-435b-a34f-9e0d20ace693
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 134f9030-a619-4229-a2ae-e2c61e9617e0
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 45e504c9-e616-4a03-b400-6e9be0faa0f8
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 42738f89-9c5f-4ae6-aa3b-3590c0312ef7
    `min_payment_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_payment_amount',
    -- column_id: bcaede65-d328-4ba3-bd0e-b10b9475a414
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
