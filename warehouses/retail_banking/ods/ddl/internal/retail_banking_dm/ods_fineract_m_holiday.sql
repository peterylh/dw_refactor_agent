-- ODS mirror of Apache Fineract m_holiday (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_holiday;
-- table_id: adeefb5f-da80-45b4-88a4-9e268bfb2b28
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_holiday (
    -- column_id: 2727fb0b-d041-40cd-bd0a-fc65d22c2ac2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a088ce02-a292-4a9d-81b5-9e79359fd363
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 232703c0-869e-4088-b4d4-5aee739fb4ff
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: f46ad45c-c603-4bf1-b977-356ac99a5616
    `to_date` DATE NOT NULL COMMENT 'Fineract source column to_date',
    -- column_id: 6666a783-8400-4758-bee8-fbcfc6f1c858
    `repayments_rescheduled_to` DATE NULL COMMENT 'Fineract source column repayments_rescheduled_to',
    -- column_id: cb37c239-e1a9-4a4d-ac9e-2327179ac213
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 1cef721d-f9e3-4f33-b1bd-6d83df65e72d
    `processed` BOOLEAN NOT NULL COMMENT 'Fineract source column processed',
    -- column_id: 680e4a6d-aefb-48d1-8f1a-ec2bb549a537
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 7f9e61fd-eec6-47ee-b81e-9752cb60c25f
    `rescheduling_type` INT NOT NULL COMMENT 'Fineract source column rescheduling_type',
    -- column_id: 723b3076-baf2-4c2a-9bac-701f357d7092
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
