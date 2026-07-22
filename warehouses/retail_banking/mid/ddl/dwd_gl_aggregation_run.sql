SET allow_partition_column_nullable = true;

-- DWD generated from m_journal_entry_aggregation_tracking
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_aggregation_run;
-- table_id: 4827b6d3-f168-4ff8-9900-33c04e2930ec
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_aggregation_run (
    -- column_id: a7bf0d85-c400-4fa8-b89d-8f364fdb195e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fdb030ef-148d-44e7-ab72-b9efc7f70fed
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 3bdf869b-49ba-4015-91f4-3b2b745dc7d3
    `aggregated_on_date_from` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date_from',
    -- column_id: a4aa4514-c7e0-41ca-875b-48fab726f900
    `aggregated_on_date_to` DATE NOT NULL COMMENT 'Fineract source column aggregated_on_date_to',
    -- column_id: 613f9015-d90e-4065-b54e-022ecb36f693
    `submitted_on_date` DATE NOT NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 520370f3-8a62-44df-a400-ed154aaa27a6
    `job_execution_id` BIGINT NOT NULL COMMENT 'Fineract source column job_execution_id',
    -- column_id: c8940144-d9a5-4a90-a4d0-f42d016d5d3c
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 371bde35-f6f0-4e41-be13-f0558010e275
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 72dfc95e-695f-4e5e-a238-8d7a4e895b57
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 540b2c46-fd38-4af8-98b5-ddbdc8cb4bf8
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: f3f846ec-4f5e-481e-a7cb-c264d9cd62e9
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
