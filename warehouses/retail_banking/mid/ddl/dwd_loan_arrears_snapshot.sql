-- DWD generated from m_loan_arrears_aging
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_arrears_snapshot;
-- table_id: c3e41ed8-72de-42cc-86cd-3274482d760d
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_arrears_snapshot (
    -- column_id: 57d2aeae-2186-4c6d-bba2-8817cf9d1371
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 8329f38c-d2e2-4a76-8580-5eceda30ddbf
    `principal_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column principal_overdue_derived',
    -- column_id: e4111d89-4aa7-4bd9-961e-9739de5cc163
    `interest_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column interest_overdue_derived',
    -- column_id: 90f3c4d7-4783-417a-9fd0-006c9bb5b40e
    `fee_charges_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column fee_charges_overdue_derived',
    -- column_id: 100b19d9-6fb3-474a-9ddc-fb9fb7cec5d9
    `penalty_charges_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column penalty_charges_overdue_derived',
    -- column_id: 69395653-6232-4e5f-a0ec-81bd40667f34
    `total_overdue_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column total_overdue_derived',
    -- column_id: 84e6c01a-88ec-435c-b5eb-2a211ffe6907
    `overdue_since_date_derived` DATE NULL COMMENT 'Fineract source column overdue_since_date_derived',
    -- column_id: 80f588e4-43b0-45d2-8a6d-879353baced7
    `snapshot_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: fce186dc-9eec-4bd6-9475-f32b3a435c8b
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`loan_id`)
DISTRIBUTED BY HASH(`loan_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
