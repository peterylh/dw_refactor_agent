-- ODS mirror of Apache Fineract m_survey_questions (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_survey_questions;
-- table_id: db3b8c67-29bc-4db4-85dd-99445fd894b7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_survey_questions (
    -- column_id: 7f849ffd-0025-4992-a808-3df6a4a3c4e0
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 18c7b8d4-3f8d-4a05-9124-051fda60ca15
    `survey_id` BIGINT NOT NULL COMMENT 'Fineract source column survey_id',
    -- column_id: f91febfb-5baa-4a14-86d7-a2f76d877a59
    `component_key` VARCHAR(32) NULL COMMENT 'Fineract source column component_key',
    -- column_id: f63d40c9-7deb-42b1-bf18-ae465a1648aa
    `a_key` VARCHAR(32) NOT NULL COMMENT 'Fineract source column a_key',
    -- column_id: d5a4679a-93fe-498f-8fd4-58c5bd50d7c5
    `a_text` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_text',
    -- column_id: 58a10de8-7519-48ac-94ad-075c09eaf3e8
    `description` VARCHAR(4000) NULL COMMENT 'Fineract source column description',
    -- column_id: 10677171-1431-4e09-99c7-3c9743440ead
    `sequence_no` INT NOT NULL COMMENT 'Fineract source column sequence_no',
    -- column_id: 39e56e64-8cf8-42e8-a843-bb578dcdcad6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
