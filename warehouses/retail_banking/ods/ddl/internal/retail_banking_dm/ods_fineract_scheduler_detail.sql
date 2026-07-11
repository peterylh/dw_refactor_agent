-- ODS mirror of Apache Fineract scheduler_detail (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_scheduler_detail;
-- table_id: 218b3d30-0614-43a6-a994-3f18aa7ca6f8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_scheduler_detail (
    -- column_id: 4654adb0-d8e6-4c5d-9289-e1650b519993
    `id` SMALLINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 11f3e995-d29b-43e9-8720-f2b2ea02ab82
    `is_suspended` BOOLEAN NOT NULL COMMENT 'Fineract source column is_suspended',
    -- column_id: da3efd1f-81a5-487f-b668-6d99651ad36c
    `execute_misfired_jobs` BOOLEAN NOT NULL COMMENT 'Fineract source column execute_misfired_jobs',
    -- column_id: e5eadffe-f7a2-4931-8144-c06ac75364af
    `reset_scheduler_on_bootup` BOOLEAN NOT NULL COMMENT 'Fineract source column reset_scheduler_on_bootup',
    -- column_id: 6b9a4f5d-f4af-4824-9717-ec3d43e6f540
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
