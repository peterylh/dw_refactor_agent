-- ODS mirror of Apache Fineract m_loan_delinquency_action (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_delinquency_action;
-- table_id: 54ce375f-d4f4-4b51-b13d-8e495d0217b8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_delinquency_action (
    -- column_id: 3f91d0cd-567e-4681-ac67-5f559d62b127
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cbbd4516-85ba-47c7-9233-accf62908b7c
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: b6f0cb9a-3397-455b-b251-488ea360339c
    `action` VARCHAR(128) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 46cebbd9-4c0f-4b5f-86f2-c6487ecfe448
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 17b9022f-625f-4eb1-82ec-f1f21079b566
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 4e2bf79d-0ab3-43d6-a191-a99091922598
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 957b2e7a-e026-4dab-ace2-447398ade43b
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a5e518f8-893b-4da4-8dcb-30d168bbd2f7
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: eafc7abd-c2a5-473d-980f-01c54e9ba41e
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 5eab52fe-16c8-4d20-a071-e3b90dd54ed3
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
