-- ODS mirror of Apache Fineract m_template (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_template;
-- table_id: 0c31d268-5d9a-46d2-ad05-0a38a1e28a2b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_template (
    -- column_id: 26cf46b5-f2fb-4844-b69c-f1df33360ba5
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 22e186f4-ae9d-4d17-8ba8-eb350d42f356
    `name` VARCHAR(255) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 29f3a642-5db6-4039-af65-e8e245ebe91a
    `text` STRING NOT NULL COMMENT 'Fineract source column text',
    -- column_id: a007f378-1b62-4459-83c1-3f8f3b10dea8
    `entity` INT NULL COMMENT 'Fineract source column entity',
    -- column_id: 6fbcec34-2e6d-4e1d-9d74-7ff82d0d2430
    `type` INT NULL COMMENT 'Fineract source column type',
    -- column_id: a7efc37c-039f-4744-90e6-4443d9aa9aa7
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
