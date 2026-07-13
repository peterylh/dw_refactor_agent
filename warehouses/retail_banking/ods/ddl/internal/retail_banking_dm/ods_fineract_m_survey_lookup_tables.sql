-- ODS mirror of Apache Fineract m_survey_lookup_tables (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_survey_lookup_tables;
-- table_id: c7925951-f652-430b-869f-9b9a4b3ee8bb
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_survey_lookup_tables (
    -- column_id: 7b45b0fd-ae16-46fe-8554-cce8b5bd3dd9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 873951ad-a6c5-401f-9b34-23dc35cfc270
    `survey_id` BIGINT NOT NULL COMMENT 'Fineract source column survey_id',
    -- column_id: d9209268-b148-4a63-b3be-defd6cadb0ad
    `a_key` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_key',
    -- column_id: d639e94f-8183-48e0-8f06-73ffacd83c94
    `description` INT NULL COMMENT 'Fineract source column description',
    -- column_id: 51b34d85-76c3-4930-8c0c-e56c192a3be3
    `value_from` INT NOT NULL COMMENT 'Fineract source column value_from',
    -- column_id: 9cfb2b9c-a03e-4bb3-bf58-0c3608ad3370
    `value_to` INT NOT NULL COMMENT 'Fineract source column value_to',
    -- column_id: 04d06e15-c3c0-4c51-8ed4-df7bd539bdaf
    `score` DECIMAL(5,2) NOT NULL COMMENT 'Fineract source column score',
    -- column_id: 1bbf4088-3cbe-478c-a4ac-e9a5c3c3d38c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
