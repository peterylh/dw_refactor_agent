-- ODS mirror of Apache Fineract m_staff_assignment_history (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_staff_assignment_history;
-- table_id: cb64c368-adbb-42a6-8f89-cc4b11e54a6a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_staff_assignment_history (
    -- column_id: 55cdf0e1-f81e-4a82-b6d3-fb975ac8b47a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: db1bc094-ff17-415b-8bdd-5cbd3e57d547
    `centre_id` BIGINT NULL COMMENT 'Fineract source column centre_id',
    -- column_id: a9e504e1-6b68-457d-ae9e-ed871c989783
    `staff_id` BIGINT NOT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: e56407dd-abce-4b7a-8d92-76ff831cf46c
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 04d05e7e-f7ad-4e83-8828-2ebcbcc4ccb0
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 498e4d06-e766-49d1-bd3c-2bd415346e30
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 4d43a2b5-8474-4725-9f74-1a412984ba1b
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 128982e4-d324-42d8-8abd-45a82258be79
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 29f6bfd8-3380-4697-a3b4-9596afd66cfb
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: 3643d5f4-635c-425e-b112-6d342acb4717
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
