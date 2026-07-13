-- ODS mirror of Apache Fineract m_wc_loan_note (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_note;
-- table_id: 0ccb53e1-ef5b-4cd0-92bd-f36d6ad228b5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_note (
    -- column_id: e0caf0cb-e8d0-4b6a-bbe2-a42a9473f0c7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 66a80653-959c-4811-b66b-4bc96b6bacd3
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: c07e10a1-4f20-4b29-b2aa-695bfb97a497
    `note` VARCHAR(1000) NULL COMMENT 'Fineract source column note',
    -- column_id: 94e86d2d-3263-4a3b-86cf-544f87c03de3
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 65382a86-7b06-445b-96ce-26e083d2b63c
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 445dc519-5421-42d4-8039-10a33e7fd744
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 9449c4f6-fcc7-457c-be41-21e3239b344d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 47824c79-4d1a-4b2e-a2aa-e55f3571e7d5
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
