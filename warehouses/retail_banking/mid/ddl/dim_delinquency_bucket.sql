-- DIM generated from m_delinquency_bucket
DROP TABLE IF EXISTS retail_banking_dm.dim_delinquency_bucket;
-- table_id: 6650b6a1-317c-48f7-af4b-2c188e512645
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_delinquency_bucket (
    -- column_id: af7828a2-04cd-4b07-82fd-d546e14aaa6d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f7185fb0-7438-41c4-a678-d36df41fdbd9
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: b36bfae6-c66e-4941-9345-67dab41f9bb1
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 30f91b76-068a-42b3-a2a1-6a783c42b885
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 540958f1-6669-4a1b-bf19-7b0144a17bec
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: bb3636b7-7707-4687-a2c5-312a9defda5e
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: eabc0130-06e7-4792-928c-440e37e00408
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 86b89758-fe04-4dce-94e5-89436f03d028
    `bucket_type` VARCHAR(50) NOT NULL COMMENT 'Fineract source column bucket_type',
    -- column_id: 6c674577-b7f7-4984-b1cd-e94c83fcbd77
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
