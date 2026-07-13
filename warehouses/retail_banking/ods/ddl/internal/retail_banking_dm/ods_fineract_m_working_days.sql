-- ODS mirror of Apache Fineract m_working_days (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_working_days;
-- table_id: 5981a8c9-de0a-4084-a43e-d2be728d28f7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_working_days (
    -- column_id: 8a49e5f6-4340-4492-bfc0-5a1ac8132d3b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0652ef95-ac91-4e86-89a7-a64e8543949c
    `recurrence` VARCHAR(100) NULL COMMENT 'Fineract source column recurrence',
    -- column_id: 9600967c-eb75-4cbf-a863-bdab821cf271
    `repayment_rescheduling_enum` SMALLINT NULL COMMENT 'Fineract source column repayment_rescheduling_enum',
    -- column_id: 7ca0d729-fa1d-49c2-8974-96843ee0435d
    `extend_term_daily_repayments` BOOLEAN NULL COMMENT 'Fineract source column extend_term_daily_repayments',
    -- column_id: f455aa1c-3e1d-4e0e-8cca-95f4fe3de8ca
    `extend_term_holiday_repayment` BOOLEAN NOT NULL COMMENT 'Fineract source column extend_term_holiday_repayment',
    -- column_id: d8f9a37a-ebdf-448e-bc0d-e964d568d4cb
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
