-- ODS mirror of Apache Fineract m_provisioning_history (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_provisioning_history;
-- table_id: 321a2363-ee21-4883-b5a9-87fcc40da881
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_provisioning_history (
    -- column_id: 275f2647-674d-4e58-94fe-096965998863
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b406938c-4143-464c-80cf-ddd0471393e6
    `journal_entry_created` BOOLEAN NULL COMMENT 'Fineract source column journal_entry_created',
    -- column_id: 3b7aa506-4745-403d-bfd1-b70e03588c03
    `createdby_id` BIGINT NULL COMMENT 'Fineract source column createdby_id',
    -- column_id: 70147795-a7ea-415f-9bfb-a629da33a081
    `created_date` DATE NULL COMMENT 'Fineract source column created_date',
    -- column_id: 9542a9db-3c1a-479e-a406-a6162471796e
    `lastmodifiedby_id` BIGINT NULL COMMENT 'Fineract source column lastmodifiedby_id',
    -- column_id: ea7ab923-9bbb-41aa-8e49-a711035f22d0
    `lastmodified_date` DATE NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 05746466-810b-445d-bb36-4535da810bbd
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
