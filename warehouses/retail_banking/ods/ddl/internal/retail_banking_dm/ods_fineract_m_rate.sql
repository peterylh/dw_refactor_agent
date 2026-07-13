-- ODS mirror of Apache Fineract m_rate (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_rate;
-- table_id: 71ea992e-7b4a-4044-b3cf-6495d8c2f638
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_rate (
    -- column_id: 1c54055f-6e54-475c-bac5-091aaa8c571d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9ed16de9-d374-41ca-a771-ca2b1685d068
    `name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 7b17fe60-9f7c-4361-b9c5-c9d2ae126941
    `percentage` DECIMAL(10,2) NOT NULL COMMENT 'Fineract source column percentage',
    -- column_id: 444b2741-cdbd-466b-9bab-9844b42f39b0
    `active` BOOLEAN NULL COMMENT 'Fineract source column active',
    -- column_id: 17e933d4-a63d-4bf7-9fcb-1a5b365e06ea
    `product_apply` SMALLINT NOT NULL COMMENT 'Fineract source column product_apply',
    -- column_id: 0402465c-69c5-453e-9cb5-dbcd3c1a48e2
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 2682df10-1789-4d0f-adf3-443b9a1d5e83
    `createdby_id` BIGINT NOT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: b9a1b17a-0da0-48e3-891d-54bc6d724c49
    `lastmodifiedby_id` BIGINT NOT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: f91495d6-29fe-43a0-a286-e9158ddc564b
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 0ec9855b-7ad9-45ff-a302-ed6a1c73ce7a
    `approve_user` BIGINT NULL COMMENT 'Fineract source column approve_user',
    -- column_id: 53225d64-448f-499b-9cf8-c83009ac6b3a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
