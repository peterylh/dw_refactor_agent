-- DWD generated from m_group_client
DROP TABLE IF EXISTS retail_banking_dm.bridge_group_customer;
-- table_id: 22e5c125-54d0-4beb-a17f-5ecea3ce7be1
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_group_customer (
    -- column_id: a00499dd-bdec-4e1c-9d27-76c759417587
    `group_id` BIGINT NOT NULL COMMENT 'Fineract source column group_id',
    -- column_id: 01719ffb-59c4-49ea-b3e6-f0e19fcefd15
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 2cc7d0c9-82af-4186-b035-8f0f8d47be0e
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`group_id`, `client_id`)
DISTRIBUTED BY HASH(`group_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
