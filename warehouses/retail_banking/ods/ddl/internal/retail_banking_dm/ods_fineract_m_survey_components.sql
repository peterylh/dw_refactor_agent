-- ODS mirror of Apache Fineract m_survey_components (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_survey_components;
-- table_id: 3238939c-407f-4329-94d2-eab5289ad0be
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_survey_components (
    -- column_id: 85f3a362-1062-4f78-b15f-472aaf6ddffb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5edbfcc6-30dd-45fe-ada2-0851295dcd0d
    `survey_id` BIGINT NOT NULL COMMENT 'Fineract source column survey_id',
    -- column_id: 2a691cda-907a-4680-b5ff-273cb14e151f
    `a_key` VARCHAR(32) NOT NULL COMMENT 'Fineract source column a_key',
    -- column_id: 7ab93158-3249-4f17-bfe9-1eb9bee60a52
    `a_text` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_text',
    -- column_id: efb0e9cf-3dd2-4716-a528-a000147b9e03
    `description` VARCHAR(4000) NULL COMMENT 'Fineract source column description',
    -- column_id: ac031bc5-c82d-49d8-aec7-f533b407eaa9
    `sequence_no` INT NOT NULL COMMENT 'Fineract source column sequence_no',
    -- column_id: ea7c1797-b863-443d-8da8-175afd360472
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
