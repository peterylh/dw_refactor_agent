SET allow_partition_column_nullable = true;

-- DWD generated from m_survey_scorecards
DROP TABLE IF EXISTS retail_banking_dm.dwd_survey_response;
-- table_id: f20ab818-ba55-49e1-8755-490dce819dd8
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_survey_response (
    -- column_id: 865fb0cd-a92d-4ab3-b4f9-3c8c5e16c8f5
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 7953f127-9ef7-4bae-a52f-7127ef679cdd
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: fce452f4-f78e-4181-92f4-13cd2a953cc5
    `survey_id` BIGINT NOT NULL COMMENT 'Fineract source column survey_id',
    -- column_id: cda0f71d-c961-49f5-bb6c-f3e2b0705a9e
    `question_id` BIGINT NOT NULL COMMENT 'Fineract source column question_id',
    -- column_id: 9b38e788-9fd3-4e15-b72b-4abc9084dab9
    `response_id` BIGINT NOT NULL COMMENT 'Fineract source column response_id',
    -- column_id: 3741d3f5-4623-460a-9130-6be3dc25efba
    `user_id` BIGINT NOT NULL COMMENT 'Fineract source column user_id',
    -- column_id: f4e57886-f312-4144-8c94-e6af5adade79
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 38bb657e-f0ab-4086-ab7a-764d5d9487d6
    `created_on` DATETIME NULL COMMENT 'Fineract source column created_on',
    -- column_id: d295d833-caf4-4fad-a6ff-ee872c60212f
    `a_value` INT NOT NULL COMMENT 'Fineract source column a_value',
    -- column_id: 3153fa64-7c21-4115-92ed-20fb66cf999d
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
