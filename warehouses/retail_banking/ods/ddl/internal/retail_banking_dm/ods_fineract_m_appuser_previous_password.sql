-- ODS mirror of Apache Fineract m_appuser_previous_password (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_appuser_previous_password;
-- table_id: aefc4a6c-c40b-4c07-84b3-a63eb2f18e8b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_appuser_previous_password (
    -- column_id: b4315c09-1d69-4bc4-bbf8-5ea51e439918
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d2bba7a1-73da-4c20-995d-0e621d3611d8
    `user_id` BIGINT NOT NULL COMMENT 'Fineract source column user_id',
    -- column_id: c3fd0362-087d-432b-9dc7-54ca06c55dab
    `password` VARCHAR(255) NOT NULL COMMENT 'Fineract source column password',
    -- column_id: 4eeb9279-a3ff-43a4-b21d-1d8c456d4ca1
    `removal_date` DATE NOT NULL COMMENT 'Fineract source column removal_date',
    -- column_id: 241c4af0-0782-41ae-910c-3c0857be40d6
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
