SET allow_partition_column_nullable = true;

-- DWD generated from m_provisioning_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_provision_run;
-- table_id: 057d48f6-a05d-445f-bcb6-f357be51d2f5
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_provision_run (
    -- column_id: 2e5b987e-ac75-43db-b70a-4355d2defa68
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 96d7c161-33c9-4f20-b633-fcddcadf1b24
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 7c0109d4-62bf-4ff0-b838-87fac8b4a719
    `journal_entry_created` BOOLEAN NULL COMMENT 'Fineract source column journal_entry_created',
    -- column_id: f9b5977c-5504-4e1a-aa59-b0db5496171b
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 0e2962e2-0df7-4f79-b324-ca0f6c790c67
    `created_date` DATE NULL COMMENT 'Fineract source column created_date',
    -- column_id: 97301323-2f21-491c-9b63-584a9103ba2e
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 0114df14-13fb-451e-9136-f4a7844721d6
    `lastmodified_date` DATE NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 13adc22a-0177-41d8-99e3-ad0c9d616543
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
