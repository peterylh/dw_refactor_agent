-- DIM generated from m_floating_rates
DROP TABLE IF EXISTS retail_banking_dm.dim_rate_index;
-- table_id: 463cd253-93f6-4c0e-a94c-857d1748050b
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_rate_index (
    -- column_id: c34fec84-d6be-422f-823d-092a7d7ef066
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f455bee2-f5c7-4c7f-a231-e76e7a6dd83a
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 81337252-0a92-4400-a690-8f9f7729b56a
    `is_base_lending_rate` BOOLEAN NOT NULL COMMENT 'Fineract source column is_base_lending_rate',
    -- column_id: b2c85b6e-bb38-4c01-b724-301c5e1d8b03
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 9cbdce76-ad98-43de-9445-74317b5be646
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 13ad43be-12f5-492c-b41e-2dd8d63f4684
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 94787046-e4e4-459b-801a-1635c4dba23f
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: e0c3dfab-23b9-4a22-aac8-e9c2f70e26dc
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 447f6506-137b-4c24-9517-96e8d081fc30
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 4b84a368-0d61-4528-92e6-16f0ac3a1091
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: dc3d26dc-0060-414e-9a4a-ce4f60943cf9
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
