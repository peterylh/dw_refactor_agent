-- ODS mirror of Apache Fineract m_survey_scorecards (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_survey_scorecards;
-- table_id: c9ef9a9b-a4f5-4040-b333-29064f69906d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_survey_scorecards (
    -- column_id: b99043d0-207e-49e3-8a43-7fa025f5fbfb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: bb9d67e0-f493-4ade-90c0-bfca4d4b54a7
    `survey_id` BIGINT NOT NULL COMMENT 'Fineract source column survey_id',
    -- column_id: b19691ac-d23d-4aea-81f5-39afa6c01112
    `question_id` BIGINT NOT NULL COMMENT 'Fineract source column question_id',
    -- column_id: 216e82a6-79ac-4e1b-a81c-c9510b16a52f
    `response_id` BIGINT NOT NULL COMMENT 'Fineract source column response_id',
    -- column_id: e7a0e071-49f8-4b9b-96f3-c5169e660f4a
    `user_id` BIGINT NOT NULL COMMENT 'Fineract source column user_id',
    -- column_id: 36c95f58-5d44-4663-9683-661cfb084815
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 9c9aa9e5-672e-4c9d-b14d-5b3166a87fe3
    `created_on` DATETIME NULL COMMENT 'Fineract source column created_on',
    -- column_id: 8370ff47-ee11-49ff-b0d7-ea4ae3526656
    `a_value` INT NOT NULL COMMENT 'Fineract source column a_value',
    -- column_id: 4479548e-3fee-4761-bdbd-6937bca98773
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
