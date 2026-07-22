SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_officer_assignment_history
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_officer_assignment;
-- table_id: 6f069f18-1ce0-47d9-8c29-f0cce3b37cf8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_officer_assignment (
    -- column_id: da3b61a4-b631-45df-883d-afd6d3105dd8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 253d153f-4d3d-4466-8c62-960b3dc464a6
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: baa95325-4d97-4867-a3c9-ebb1a6e8a542
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: afef3f92-792a-49b4-b27f-0852930ce7a9
    `loan_officer_id` BIGINT NULL COMMENT 'Fineract source column loan_officer_id',
    -- column_id: 94b8d56f-cd5f-4e2b-a409-2e77f6d7c8b1
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 7dccf4ed-e730-4580-b7d0-944192ca7cdb
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: fbf2640c-64c8-4603-95c6-8351e8b87d24
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 89d65a00-8b55-48b9-ab00-3a25ed8e30f3
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: fafc3f74-0302-40f9-a949-76801ac86bfc
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 5dd6e73f-03bb-4c40-a0ac-7987b876a4e4
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: a6f73880-e2da-438f-819c-0fb75e2feb86
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
