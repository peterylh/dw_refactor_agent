-- ODS mirror of Apache Fineract m_delinquency_bucket_mappings (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_delinquency_bucket_mappings;
-- table_id: 4949296d-534d-4a09-a7ac-2a3baf3e2fac
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_delinquency_bucket_mappings (
    -- column_id: fcfd7d53-3c27-435e-90b9-ad57420d9980
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a4c54f60-8cfe-46f4-b785-d51bf441d192
    `delinquency_range_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_range_id',
    -- column_id: b6f9266a-22f9-475a-b976-49a89bba7512
    `delinquency_bucket_id` BIGINT NOT NULL COMMENT 'Fineract source column delinquency_bucket_id',
    -- column_id: 8e8100d1-d546-4880-a5ed-66dac5e9273a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e31a51ef-d659-4d08-be55-e11cfd8acdf9
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: b8f82c94-92a6-4cfe-828f-9850b8bec69a
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: ef9fa752-11f9-4722-93b5-52818c70d2a6
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: a813cb85-1e99-4486-adef-e4e456c34541
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: c2d8d4cb-8ff1-43d9-a1db-dd062435907f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
