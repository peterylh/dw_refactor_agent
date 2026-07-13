-- DWD generated from acc_gl_closure
DROP TABLE IF EXISTS retail_banking_dm.dwd_gl_close_event;
-- table_id: 330127b5-b1eb-4821-9eaa-96c2ea245915
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_gl_close_event (
    -- column_id: 4a7cf1e0-a0ed-45cc-9e25-a55a87a03216
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 52601f8b-dc74-4149-be0d-64f6f3eead2e
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: ce9b51bf-5892-4656-858b-883f837ca60d
    `closing_date` DATE NOT NULL COMMENT 'Fineract source column closing_date',
    -- column_id: 761625d9-772e-4205-a28d-756e413e55c9
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 16f5b76f-0c2a-40d8-8bc3-dd21551aa0f6
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 02c859b9-78c8-42e3-9198-f7e4f12a18e0
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 5c9c9e73-c6ea-475e-91b5-88b1d75a41fd
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 3d40c189-254c-4efb-abaf-d159b7f620a3
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: b2cd0b25-0a06-41eb-95d2-85d9fcaf8662
    `comments` VARCHAR(500) NULL COMMENT 'Fineract source column comments',
    -- column_id: 0d9ce662-b868-4335-9411-ba5d75fbc025
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: ef46f222-220c-4d24-bb2e-3181a2023f17
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
