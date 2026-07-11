-- ODS mirror of Apache Fineract m_hook_registered_events (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_hook_registered_events;
-- table_id: c395530a-33ba-4c97-bbde-9695a1b7280d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_hook_registered_events (
    -- column_id: 8c3e0298-af53-4706-a00c-09be83d3a118
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1f642208-2957-4661-93f2-675137be1e31
    `hook_id` BIGINT NOT NULL COMMENT 'Fineract source column hook_id',
    -- column_id: c2219a3e-4f6b-43d0-ae59-ba15bedaaf26
    `entity_name` VARCHAR(45) NOT NULL COMMENT 'Fineract source column entity_name',
    -- column_id: 66a117a9-8639-44be-a81e-04ffd58931e8
    `action_name` VARCHAR(45) NOT NULL COMMENT 'Fineract source column action_name',
    -- column_id: 46219e9f-b608-4dd3-9d38-ac275438f757
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
