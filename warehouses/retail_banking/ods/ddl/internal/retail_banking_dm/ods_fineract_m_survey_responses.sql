-- ODS mirror of Apache Fineract m_survey_responses (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_survey_responses;
-- table_id: 5e9232e5-d0df-45b9-a8c9-f5790c394980
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_survey_responses (
    -- column_id: 62a04f1f-ac1a-48bd-b7a3-2bc5448ec8c6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a1fee5ed-d82a-42b1-bd6a-0e8a18bad724
    `question_id` BIGINT NOT NULL COMMENT 'Fineract source column question_id',
    -- column_id: 2db87832-ee52-44d3-b723-2732a8506bd3
    `a_text` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_text',
    -- column_id: b8999ef7-5edd-4561-9341-d4747a8038c3
    `a_value` INT NOT NULL COMMENT 'Fineract source column a_value',
    -- column_id: 328ead10-5f46-4447-939c-81b44b6f16af
    `sequence_no` INT NOT NULL COMMENT 'Fineract source column sequence_no',
    -- column_id: dd92b6a4-4476-40bc-a650-f1953f7555ac
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
