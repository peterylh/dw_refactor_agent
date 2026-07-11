-- ODS mirror of Apache Fineract m_calendar_history (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_calendar_history;
-- table_id: dde42ec9-6099-41ca-9322-4d5dc35ef143
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_calendar_history (
    -- column_id: 59b67889-fb88-4654-b315-ba61c3070e23
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: ddba4f44-bbbf-4b91-b55e-52ec1ce75bdc
    `calendar_id` BIGINT NOT NULL COMMENT 'Fineract source column calendar_id',
    -- column_id: d87261e2-33b8-43a9-8343-c75c4c12171f
    `title` VARCHAR(70) NOT NULL COMMENT 'Fineract source column title',
    -- column_id: 5ee5f40e-3644-4465-b670-aadbad3cf673
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: f28fc4e6-b187-4a6a-964e-bd4aea7c2085
    `location` VARCHAR(50) NULL COMMENT 'Fineract source column location',
    -- column_id: 28bc334c-839c-41ee-8d3a-6b8361ebaaf7
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: d99e410a-a59d-4855-8546-ac2331975f1d
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: c062a626-f2cf-427f-ae8c-c613350302cf
    `duration` SMALLINT NULL COMMENT 'Fineract source column duration',
    -- column_id: ed1c5cb0-5606-497d-ae4f-3b19c5723432
    `calendar_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column calendar_type_enum',
    -- column_id: a88f7aa4-9167-4338-82ba-151a4cb33a20
    `repeating` BOOLEAN NOT NULL COMMENT 'Fineract source column repeating',
    -- column_id: da7bfbc4-31a2-4c28-8572-dbffe16b8b3a
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: 512a9eba-5300-4d25-a9cd-c98f2f9be2fb
    `remind_by_enum` SMALLINT NULL COMMENT 'Fineract source column remind_by_enum',
    -- column_id: 67dd9d73-87d6-421c-b200-1de286a73160
    `first_reminder` SMALLINT NULL COMMENT 'Fineract source column first_reminder',
    -- column_id: cdf8707e-ef2a-4ee0-972e-87aa16592624
    `second_reminder` SMALLINT NULL COMMENT 'Fineract source column second_reminder',
    -- column_id: 75c5f390-2390-41a0-bed5-36d166a3043e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
