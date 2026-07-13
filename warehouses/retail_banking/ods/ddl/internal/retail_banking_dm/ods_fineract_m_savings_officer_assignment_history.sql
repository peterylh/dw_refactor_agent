-- ODS mirror of Apache Fineract m_savings_officer_assignment_history (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_officer_assignment_history;
-- table_id: 1a1afa1e-a8e5-49d3-aab9-5e3491548050
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_officer_assignment_history (
    -- column_id: 42c73029-1228-4c25-8c47-d362cee433f6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a937e1d2-56cd-4980-85c4-a35a2328672c
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: ed9ae7eb-bc2a-488e-ad78-38d96e501929
    `savings_officer_id` BIGINT NULL COMMENT 'Fineract source column savings_officer_id',
    -- column_id: 123273cd-004c-430e-847f-5faa73aa28ea
    `start_date` DATE NOT NULL COMMENT 'Fineract source column start_date',
    -- column_id: 9c2d11ea-aa39-4eb0-8887-8bfd571cdc3c
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 4274921c-0cfb-496c-99f7-da46cca2ebb6
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 3618d773-dc52-44db-8e1a-9b92ed186f6e
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: b66d3d2e-ede8-4248-883f-4f6b6688b1c8
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: f7e234b2-5c95-48b9-9152-fb67ed4905c7
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 88ac8fd3-64de-4abc-9c99-e7cc61e775f2
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 419e11d4-aac0-4ef8-8f9d-7b9728758364
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 99e29830-d286-44c2-a91b-dc4efbf3db5e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
