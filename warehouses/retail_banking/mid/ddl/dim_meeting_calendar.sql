-- DIM generated from m_calendar
DROP TABLE IF EXISTS retail_banking_dm.dim_meeting_calendar;
-- table_id: d1f45c93-c2f2-4ab2-b81e-bf216f5c0aaa
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_meeting_calendar (
    -- column_id: 4564832f-d408-40b3-b735-ebeb3aad5aec
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 98c8e0c1-4e7d-495f-b5ee-aff1434dea61
    `title` VARCHAR(70) NOT NULL COMMENT 'Fineract source column title',
    -- column_id: 9b1c9ac6-879a-4f5c-bfac-816d39596a69
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 76768748-f84a-46fe-ae4d-47639a29418d
    `location` VARCHAR(50) NULL COMMENT 'Fineract source column location',
    -- column_id: e10a2cd3-d30f-4ab0-8869-2cec49f144a2
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 1e98b073-150b-4bc4-960e-9cffc1a145cc
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 36e47cfd-2a69-4e07-bdd3-64a7544a72f4
    `duration` SMALLINT NULL COMMENT 'Fineract source column duration',
    -- column_id: 2c440687-a895-4f08-9377-e99165171306
    `calendar_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column calendar_type_enum',
    -- column_id: 08f185a3-81d3-42bc-9182-eb5d42df256d
    `repeating` BOOLEAN NOT NULL COMMENT 'Fineract source column repeating',
    -- column_id: 0d42ff9d-e7ac-4ed6-bd10-6fb35cf9d87e
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: b10b7f02-288a-4031-831f-d96ac6c757a4
    `remind_by_enum` SMALLINT NULL COMMENT 'Fineract source column remind_by_enum',
    -- column_id: 4a1eeec2-6003-4129-a8a6-e6bf53001182
    `first_reminder` SMALLINT NULL COMMENT 'Fineract source column first_reminder',
    -- column_id: a928519d-0678-4bb5-9328-e3f9e919268d
    `second_reminder` SMALLINT NULL COMMENT 'Fineract source column second_reminder',
    -- column_id: 0834a515-3742-416e-8fdc-6110f0e772ac
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 1200f72c-c2ab-45f5-b4df-8321c36c5bed
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a48013fa-c377-45a5-9880-8588fac56b55
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: feaf93f0-3fe1-47f1-86cd-42a20226b755
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 50031733-55eb-49d7-abfd-b70a29186e6c
    `meeting_time` STRING NULL COMMENT 'Fineract source column meeting_time',
    -- column_id: 56d6ead5-154a-4ed3-a0b6-1507fca7314e
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 86467054-812d-46e6-99de-c210f90f563f
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 604c3bf1-bce8-4847-8160-43549d8c722a
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
