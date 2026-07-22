SET allow_partition_column_nullable = true;

-- DWD generated from m_staff_assignment_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_staff_assignment;
-- table_id: 2f7ffb8e-3f59-4214-b66c-e69d9760c748
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_staff_assignment (
    -- column_id: b62631fd-11bc-4605-85b5-9c24f20e7caf
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 681225c8-266a-4623-b965-89394a074f38
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 7b5a588a-bbab-4e99-b106-c613adc44aba
    `centre_id` BIGINT NULL COMMENT 'Fineract source column centre_id',
    -- column_id: c62af63c-5b2d-458d-bbf0-0030b049bb66
    `staff_id` BIGINT NOT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 21a072fb-93ee-4f28-9d1b-490eb1071122
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 30d0176f-42ee-418c-a64c-89e44b860e31
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 91395199-4b53-4ed2-9e2d-ac270598830e
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 976b614c-81f8-4cce-9071-556dd739e192
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: d07b7db5-60cd-4343-a43e-1343a7b1b9c2
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: ca04c338-0277-4b18-ab2c-6d163620f2c1
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 538afb43-4374-4f77-a23c-45da802188a8
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
