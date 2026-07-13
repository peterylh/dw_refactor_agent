-- ODS mirror of Apache Fineract m_wc_loan_near_breach_action (营运资金贷款)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_wc_loan_near_breach_action;
-- table_id: 1de381c0-1a25-4cff-9a2b-d0a356f1e832
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_wc_loan_near_breach_action (
    -- column_id: f0ac3c4b-351c-4858-b1c1-578c73686cc6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 78425317-fa91-4ae2-982a-ca883b6f139d
    `wc_loan_id` BIGINT NOT NULL COMMENT 'Fineract source column wc_loan_id',
    -- column_id: c3fdf482-8c73-4d36-9d39-23e14cb61561
    `action` VARCHAR(50) NOT NULL COMMENT 'Fineract source column action',
    -- column_id: 8a874db2-557a-40b3-be47-d67eb5775263
    `threshold` DECIMAL(19,6) NULL COMMENT 'Fineract source column threshold',
    -- column_id: 4fdf6c51-c54b-4f98-afde-dbf4fb4c0a53
    `frequency` INT NULL COMMENT 'Fineract source column frequency',
    -- column_id: 8c65c85d-0382-4e1c-8f14-2e219d7cc393
    `frequency_type` VARCHAR(50) NULL COMMENT 'Fineract source column frequency_type',
    -- column_id: ae6d1f27-a6ba-4ac3-ad1e-d15211dcef79
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: b3149da8-1f6f-49c0-921e-ff2e3ff00305
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 30a9127f-6edb-4e10-846e-0c9736252c72
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c9d935e7-f322-4973-89f8-ce8e9786cfb3
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 1a132527-e1ea-4cde-b15e-93565dce7d7a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
