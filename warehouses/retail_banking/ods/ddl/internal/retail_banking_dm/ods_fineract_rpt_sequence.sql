-- ODS mirror of Apache Fineract rpt_sequence (其它银行运营)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_rpt_sequence;
-- table_id: 8a7d1bb0-fc3a-4ac2-a740-8c180bd3b6ab
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_rpt_sequence (
    -- column_id: c1d10f70-28a4-408d-860d-4b6fecc426ea
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 981a18f3-8268-4323-9cf6-a2ea124d60bf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
