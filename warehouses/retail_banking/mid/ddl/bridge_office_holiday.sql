SET allow_partition_column_nullable = true;

-- DWD generated from m_holiday_office
DROP TABLE IF EXISTS retail_banking_dm.bridge_office_holiday;
-- table_id: 12c90243-065d-4108-8cd3-4d6c415bdcc5
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_office_holiday (
    -- column_id: 4343280b-f4c1-4a81-b631-d9e2c88fd1d6
    `holiday_id` BIGINT NOT NULL COMMENT 'Fineract source column holiday_id',
    -- column_id: 4e12464a-41ee-437f-80c5-771d718431d0
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 190af395-3437-426a-b2b5-09bfbfedeb94
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 4f24d252-76b1-43cb-a2bd-30a6c33fc9c4
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`holiday_id`, `office_id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`holiday_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
