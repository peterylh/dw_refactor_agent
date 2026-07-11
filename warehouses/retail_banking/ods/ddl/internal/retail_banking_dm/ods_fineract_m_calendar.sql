-- ODS mirror of Apache Fineract m_calendar (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_calendar;
-- table_id: 0d1fd8b0-1e73-49b5-a627-c78dbc18b06b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_calendar (
    -- column_id: c42f5617-920a-43c4-b9f6-1ee147bb66c6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 324cb553-6a2d-426a-8efd-a1902b7d2e4a
    `title` VARCHAR(70) NOT NULL COMMENT 'Fineract source column title',
    -- column_id: 58c7c233-d866-4940-b8f1-520ebc780854
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: c83dd8c2-e3c2-467b-af5c-547d0a86a244
    `location` VARCHAR(50) NULL COMMENT 'Fineract source column location',
    -- column_id: 991940ce-84ef-4c74-bfe9-0e6da873a35e
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: f8e41ff2-e0ac-482f-9b9c-1c46f3d4ccaa
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 32f976a1-1f0a-49ac-81a9-0266262c68da
    `duration` SMALLINT NULL COMMENT 'Fineract source column duration',
    -- column_id: cfe56efd-07ae-4da3-8803-2d3a7c0912cd
    `calendar_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column calendar_type_enum',
    -- column_id: d4bcf69e-a521-46c8-b2fc-0023518daace
    `repeating` BOOLEAN NOT NULL COMMENT 'Fineract source column repeating',
    -- column_id: 6dee1e74-ac33-4443-9d29-776a5479a6b6
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: 3228f659-c9e6-4a39-a431-6df9ff4451b1
    `remind_by_enum` SMALLINT NULL COMMENT 'Fineract source column remind_by_enum',
    -- column_id: 3e30b1bc-fecc-4f74-a4f7-cd8882b41433
    `first_reminder` SMALLINT NULL COMMENT 'Fineract source column first_reminder',
    -- column_id: 41f4d7e3-75e9-4f1c-b49f-808d5c30d6b5
    `second_reminder` SMALLINT NULL COMMENT 'Fineract source column second_reminder',
    -- column_id: 95d9d042-201f-420c-9f19-8a9b3b145860
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: f4cfb01e-e6a6-4b5e-83d9-f2d65df9bea9
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 589be223-1db6-412c-964e-fbf49f1b6b03
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: e1343709-9f08-40c7-b371-71505b89b8b2
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 8691893f-c735-435e-a963-c08f629d9ec5
    `meeting_time` STRING NULL COMMENT 'Fineract source column meeting_time',
    -- column_id: 927e826d-7d40-49ce-9f92-bef9a7a22e34
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 6c9d227e-6968-465b-89a8-ea2242fe00c9
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 89d19e49-60f9-44ad-bf2c-43c0a180114d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
