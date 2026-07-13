-- ODS mirror of Apache Fineract m_wc_loan_range_delinquency_tag (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_range_delinquency_tag;
-- table_id: 680a1271-a770-4687-b654-8c33c9f73642
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_range_delinquency_tag (
    -- column_id: e12bd531-4dd7-4610-a96c-589cf6d066c9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3266549f-0313-47cd-8f05-97e1e02dca24
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 96ccc4c4-a5e5-4175-b963-30e2ee2c38fd
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 2e96c7b4-5db5-41ee-a8af-c73f5301fe7d
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: b551c2bb-7717-4559-b728-ec8fff342864
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 793b2530-1742-44e6-94c6-5b550c48d9fe
    `range_id` BIGINT NOT NULL COMMENT 'Fineract source column range_id',
    -- column_id: 1b617335-26b9-4422-a024-0913db88c005
    `addedon_date` DATE NOT NULL COMMENT 'Fineract source column addedon_date',
    -- column_id: c2f48afe-50cf-4bfc-83ef-45e9037e283c
    `liftedon_date` DATE NULL COMMENT 'Fineract source column liftedon_date',
    -- column_id: 49b9f5d9-679e-4a86-8294-28901736d836
    `outstanding_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column outstanding_amount',
    -- column_id: f3b0b2fe-03c7-4b2e-828c-f8d8e1ab4947
    `version` BIGINT NULL COMMENT 'Fineract source column version',
    -- column_id: 80322a75-bcef-448f-a61d-c1496b1b47ac
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 67f174a9-d399-4643-9f24-4f38496a062c
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 3f50427c-9ec6-4210-a26a-c14737ae56e3
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
