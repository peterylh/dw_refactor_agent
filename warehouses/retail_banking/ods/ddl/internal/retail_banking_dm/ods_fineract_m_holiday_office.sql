-- ODS mirror of Apache Fineract m_holiday_office (机构与员工)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_holiday_office;
-- table_id: 0ad7fdb3-a19c-4aec-8c17-c1c0ba4a11ac
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_holiday_office (
    -- column_id: 2506bd4c-15e0-4694-8147-cb5ce9f88929
    `holiday_id` BIGINT NOT NULL COMMENT 'Fineract source column holiday_id',
    -- column_id: bcffe686-c70d-41c7-b5ed-7ac1c4bfdde8
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 86b2dac4-1352-4667-8d40-90621fdb7241
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`holiday_id`, `office_id`)
DISTRIBUTED BY HASH(`holiday_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
