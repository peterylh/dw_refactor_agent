-- DIM generated from m_delinquency_range
DROP TABLE IF EXISTS retail_banking_dm.dim_delinquency_range;
-- table_id: 1d9afb24-ba67-4022-8165-3508a5b57e5f
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_delinquency_range (
    -- column_id: 37a53b94-94f0-4d75-8b6e-0bf44db87a9e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 083814f0-2ad2-4cdd-a309-8e876af7d5ea
    `classification` VARCHAR(100) NOT NULL COMMENT 'Fineract source column classification',
    -- column_id: 3bf4e572-2511-4e0c-a968-f16d3b89cbea
    `min_age_days` BIGINT NOT NULL COMMENT 'Fineract source column min_age_days',
    -- column_id: 021bbec2-5ada-446a-8db9-6ec6f7699e83
    `max_age_days` BIGINT NULL COMMENT 'Fineract source column max_age_days',
    -- column_id: cb91132a-bca7-48b8-996e-ac8183716b7a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 4c6e8519-67cd-452e-a71d-350a9d41612b
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: f2b70c26-bbfb-4478-b8c2-ae5259b3d19c
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: dddd2df4-23ff-4ad9-845f-bb8ae287f5eb
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 43f63924-6763-49bf-af27-97d6d1353fb3
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 95ce4c85-c588-4b8c-a9ff-08652aded37d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
