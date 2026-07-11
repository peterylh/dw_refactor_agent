-- DWD generated from m_external_asset_owner_transfer
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_ownership_transfer;
-- table_id: a75bce20-c404-41a5-b0bd-8b3d76ca6e36
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_ownership_transfer (
    -- column_id: ce433624-53a9-4247-83e2-9bf88e0c8b34
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: bf658134-8713-4686-8a4d-1a7c97a56dc1
    `owner_id` BIGINT NOT NULL COMMENT 'Fineract source column owner_id',
    -- column_id: d135eed0-d8c1-44fe-ace4-5f066831d3e1
    `external_id` VARCHAR(64) NOT NULL COMMENT 'Fineract source column external_id',
    -- column_id: 596c066e-821c-4377-9742-19bb40b7b5d8
    `status` VARCHAR(50) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: 3730c7df-20a1-404b-a95a-b39e7d5f4877
    `purchase_price_ratio` VARCHAR(50) NOT NULL COMMENT 'Fineract source column purchase_price_ratio',
    -- column_id: 53c5c02c-4ebb-4826-884e-096e9f3c5d54
    `settlement_date` DATE NOT NULL COMMENT 'Fineract source column settlement_date',
    -- column_id: ab2a7239-2fff-464b-a9c4-52dc9af8b003
    `effective_date_from` DATE NOT NULL COMMENT 'Fineract source column effective_date_from',
    -- column_id: a0d8c59e-7095-48fc-815c-90c6315d3c07
    `effective_date_to` DATE NOT NULL COMMENT 'Fineract source column effective_date_to',
    -- column_id: 0470954c-3507-480f-87f6-636550d7c72c
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 417abcb0-7e34-4ee9-95e2-bde1621e7878
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c0622d0d-532c-4be3-8b2e-53e6c91cf59e
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 3a85b870-a38f-4dc5-a31e-52a5700f8f34
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: a8505fce-8761-4e93-a6e0-54caf82b015f
    `external_loan_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_loan_id',
    -- column_id: 112b3225-4b7c-41db-aadc-3363838e8927
    `loan_id` BIGINT NOT NULL COMMENT 'Loan ID',
    -- column_id: e8fe9800-5372-4149-ad38-164a56b7b8f5
    `sub_status` VARCHAR(50) NULL COMMENT 'Fineract source column sub_status',
    -- column_id: 0220b9cd-87ba-4398-a502-3d19c04268d5
    `external_group_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_group_id',
    -- column_id: 337e4397-41c0-4a72-ad3a-25685fddfc7a
    `previous_owner_id` BIGINT NULL COMMENT 'Fineract source column previous_owner_id',
    -- column_id: bbe15ba8-e81b-4fa3-999d-432f12b72255
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 3bed4040-4493-4e18-9e0e-9102fb67bf38
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
