-- ODS mirror of Apache Fineract m_command (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_command;
-- table_id: a4dadad1-8e93-4303-b941-5616267a3885
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_command (
    -- column_id: ccbe0abd-8649-471a-a5a1-e238f326abe9
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 8a7cf037-8400-470b-89ad-bc7956577b66
    `created_at` DATETIME NULL COMMENT 'Fineract source column created_at',
    -- column_id: 974abfcf-b490-4bb8-a866-b49f243ec9fe
    `command_id` VARCHAR(36) NULL COMMENT 'Fineract source column command_id',
    -- column_id: b7be5825-5eab-464f-9131-46c13f511646
    `tenant_id` VARCHAR(255) NULL COMMENT 'Fineract source column tenant_id',
    -- column_id: ac510fe5-23c6-42dc-822c-da0de1679b08
    `initiated_by_username` VARCHAR(255) NULL COMMENT 'Fineract source column initiated_by_username',
    -- column_id: 4ab6b483-b258-42dd-9fc3-ede99eb54432
    `request` STRING NULL COMMENT 'Fineract source column request',
    -- column_id: ab498695-4aa1-4040-888e-5f5d7ae0a51a
    `updated_at` DATETIME NULL COMMENT 'Fineract source column updated_at',
    -- column_id: c9079de6-abbd-42f7-a4d7-6d7117323bbf
    `executed_at` DATETIME NULL COMMENT 'Fineract source column executed_at',
    -- column_id: 648b0cc3-ea6b-438c-8dff-ac9c6ad02a3c
    `approved_at` DATETIME NULL COMMENT 'Fineract source column approved_at',
    -- column_id: 3a67a269-8a17-4993-aca3-2c68c295b319
    `rejected_at` DATETIME NULL COMMENT 'Fineract source column rejected_at',
    -- column_id: 6c94bba2-c195-4388-8178-a39d964a1efd
    `idempotency_key` VARCHAR(255) NULL COMMENT 'Fineract source column idempotency_key',
    -- column_id: c731fe50-a31e-4681-9c63-e37b4a210510
    `executed_by_username` VARCHAR(255) NULL COMMENT 'Fineract source column executed_by_username',
    -- column_id: bb85cd60-8b23-49f1-9a85-ccee690e3cfe
    `approved_by_username` VARCHAR(255) NULL COMMENT 'Fineract source column approved_by_username',
    -- column_id: c401840b-1ccb-4584-9c0e-fa3a10b71cff
    `rejected_by_username` VARCHAR(255) NULL COMMENT 'Fineract source column rejected_by_username',
    -- column_id: 4d2eee2d-d454-44ac-a5ba-c08f875ada29
    `ip_address` VARCHAR(255) NULL COMMENT 'Fineract source column ip_address',
    -- column_id: 7a3456e9-050e-4b92-95fb-5238c2abe4a6
    `state` VARCHAR(255) NULL COMMENT 'Fineract source column state',
    -- column_id: 17ba9580-4670-45c2-83de-51ce48277eeb
    `response` STRING NULL COMMENT 'Fineract source column response',
    -- column_id: 1ab1e8df-71e2-4391-bf25-d25d3787cf05
    `error` STRING NULL COMMENT 'Fineract source column error',
    -- column_id: 958af428-5e7d-40aa-a37a-ed95640d8eaf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
