-- ODS mirror of Apache Fineract m_collateral_management (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_collateral_management;
-- table_id: 1a13ac57-8036-425d-a324-5d3c37098582
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_collateral_management (
    -- column_id: af246285-23ff-4b6e-9f86-d38ab3178a27
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: edf843e3-3219-4237-8997-18e9d46a2b69
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: cfca7449-1a96-467a-a22e-99f27f2959e9
    `quality` VARCHAR(40) NOT NULL COMMENT 'Fineract source column quality',
    -- column_id: 94d43b1a-4d7f-4672-a1e0-b89d5d54174e
    `base_price` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column base_price',
    -- column_id: 007ccc3c-7621-4265-9255-52d4f395895b
    `unit_type` VARCHAR(10) NOT NULL COMMENT 'Fineract source column unit_type',
    -- column_id: b8294fd3-6adc-4ecb-9ede-dc27cba3c468
    `pct_to_base` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column pct_to_base',
    -- column_id: b81c772c-4c82-439f-bcf2-4835ccd189fa
    `currency` BIGINT NULL COMMENT 'Fineract source column currency',
    -- column_id: 4928fd8f-fdb1-44be-b801-23072210e799
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
