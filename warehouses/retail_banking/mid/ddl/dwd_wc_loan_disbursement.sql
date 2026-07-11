-- DWD generated from m_wc_loan_disbursement_detail
DROP TABLE IF EXISTS retail_banking_dm.dwd_wc_loan_disbursement;
-- table_id: 98cbc02a-68da-4ad8-8306-770343eecab7
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_wc_loan_disbursement (
    -- column_id: e51322ca-0547-4456-8dc3-d2c8539b9706
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: db80127e-3c2e-4c72-970b-f78206ba6e64
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: 5c9843cb-bb2e-480a-9da5-31382842cef3
    `expected_disburse_date` DATE NULL COMMENT 'Fineract source column expected_disburse_date',
    -- column_id: faf02872-d3f3-4396-80c1-afb9c664b10a
    `expected_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column expected_amount',
    -- column_id: db333a2e-1fcc-4e85-a6f0-0c0115f809dc
    `expected_maturity_date` DATE NULL COMMENT 'Fineract source column expected_maturity_date',
    -- column_id: ef47071a-9492-43fa-bacf-825bfc98a38e
    `actual_disburse_date` DATE NULL COMMENT 'Fineract source column actual_disburse_date',
    -- column_id: a5d3b36d-cb48-4627-ad1c-47baba9fabcc
    `actual_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column actual_amount',
    -- column_id: e59d2ec7-ef3f-4c5c-8785-08f9f30e3dcd
    `disbursedon_userid` BIGINT NULL COMMENT 'Fineract source column disbursedon_userid',
    -- column_id: 7832b281-fd18-445f-a78d-9ec6f5bfb5f8
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 0706a4c8-78f1-4e7d-911d-cb1d3552aed3
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
