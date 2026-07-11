-- ODS mirror of Apache Fineract m_loan_officer_assignment_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_officer_assignment_history;
-- table_id: 1da07b66-c139-4322-a5e4-b62d426c327f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_officer_assignment_history (
    -- column_id: 392df241-8ed9-4a08-9ef5-ff7861a88c9f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 75da9dfd-4295-49eb-9330-951c19c4b91a
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 34d27ff7-98c3-4440-ae6f-90afc0fdfae7
    `loan_officer_id` BIGINT NULL COMMENT 'Fineract source column loan_officer_id',
    -- column_id: 5a97bba5-497e-43dd-b317-62bcef849e24
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 8bbac499-d827-41a0-9e17-3da32c7ef967
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: ffffa0ca-5619-4c2c-bfe6-31631dc96186
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: a493d8ea-65cf-4d5d-9940-1771a9e29395
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: aca88b46-c10c-4140-aba1-df1e592e9d50
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 352c1192-e33a-4917-9d30-7b3464ce129f
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 1ebc33e5-1589-4458-9f86-18a4307e2992
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
