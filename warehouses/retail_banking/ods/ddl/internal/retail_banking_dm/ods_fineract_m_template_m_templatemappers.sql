-- ODS mirror of Apache Fineract m_template_m_templatemappers (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_template_m_templatemappers;
-- table_id: 52bc3e1a-28f8-4cad-b7f7-08faf2055f71
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_template_m_templatemappers (
    -- column_id: 80d28d5d-95e0-4429-aa32-e3ce87475717
    `m_template_id` BIGINT NOT NULL COMMENT 'Fineract source column m_template_id',
    -- column_id: 02b1bdcd-c579-4456-92ad-67f884f6b55c
    `mappers_id` BIGINT NOT NULL COMMENT 'Fineract source column mappers_id',
    -- column_id: 4f563be1-9459-4b74-a393-582c37d02471
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`m_template_id`)
DISTRIBUTED BY HASH(`m_template_id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
