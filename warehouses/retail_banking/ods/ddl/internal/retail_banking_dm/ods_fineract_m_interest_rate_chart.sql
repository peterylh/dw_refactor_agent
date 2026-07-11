-- ODS mirror of Apache Fineract m_interest_rate_chart (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_interest_rate_chart;
-- table_id: 714a13f6-e6a8-46d7-89fd-3fa5e124843a
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_interest_rate_chart (
    -- column_id: a129bff0-ea8a-4d54-a9d0-f81a5bf35b0e
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3b6e1dd6-65e0-4dcc-8c2c-6ff68b62e45c
    `name` VARCHAR(100) NULL COMMENT 'Fineract source column name',
    -- column_id: fd9e1e6a-9b96-4ea6-952e-ebf6e04f921f
    `description` VARCHAR(200) NULL COMMENT 'Fineract source column description',
    -- column_id: 13cfe1d2-9e59-4b06-8fa9-ed3a253f9a3d
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: c92305cb-349a-438c-bc3b-99726f772b22
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 62a10cc4-82ff-478c-a4b0-d652ddf3a46f
    `is_primary_grouping_by_amount` BOOLEAN NOT NULL COMMENT 'Fineract source column is_primary_grouping_by_amount',
    -- column_id: de99c434-3c2f-4556-8b7d-9dd79d95e783
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
