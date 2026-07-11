-- ODS mirror of Apache Fineract m_external_asset_owner_transfer (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer;
-- table_id: 1f1de228-263b-42ab-ba97-d75e475c0218
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_external_asset_owner_transfer (
    -- column_id: b3c3c2e8-797e-4995-9f92-d22638ca71e7
    `id` BIGINT NOT NULL COMMENT 'Internal ID',
    -- column_id: 60afbc74-6e72-4742-8d8e-da707c96c8ad
    `owner_id` BIGINT NOT NULL COMMENT 'Fineract source column owner_id',
    -- column_id: 2a461aa3-642f-437a-8d82-87d47da18fe9
    `external_id` VARCHAR(100) NOT NULL COMMENT 'Fineract source column external_id',
    -- column_id: 927d8fc6-b6ab-4012-9a28-1d30ccf416ec
    `status` VARCHAR(50) NOT NULL COMMENT 'Fineract source column status',
    -- column_id: e360fbf1-e614-44dc-8d89-e5934c3dad9b
    `purchase_price_ratio` VARCHAR(50) NOT NULL COMMENT 'Fineract source column purchase_price_ratio',
    -- column_id: ea230859-fcc6-4598-9d9a-e62f697af5b0
    `settlement_date` DATE NOT NULL COMMENT 'Fineract source column settlement_date',
    -- column_id: 0cdff03f-cb19-4164-ad8c-9a7e8e9d4a13
    `effective_date_from` DATE NOT NULL COMMENT 'Fineract source column effective_date_from',
    -- column_id: cf544808-dff7-4658-aa9e-eb01cbe9fdb7
    `effective_date_to` DATE NOT NULL COMMENT 'Fineract source column effective_date_to',
    -- column_id: 8716c50e-1345-4125-8f67-a6bedb3ca2e9
    `created_by` BIGINT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 30e5a866-7e6a-4936-8a21-f1dea5be5567
    `created_on_utc` DATETIME NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 2fd9d794-11b5-41c8-b10c-77d58c5175a6
    `last_modified_by` BIGINT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8cede488-8b57-4edb-ae53-e9953ba61a05
    `last_modified_on_utc` DATETIME NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 3551025d-a8a5-4c95-9190-58bef8fa5f8e
    `external_loan_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_loan_id',
    -- column_id: 3d575303-e580-4164-93a9-64f5ff17085a
    `loan_id` BIGINT NOT NULL COMMENT 'Loan ID',
    -- column_id: 0a939516-71c2-49e6-93e1-5d894590bc93
    `sub_status` VARCHAR(50) NULL COMMENT 'Fineract source column sub_status',
    -- column_id: ff861cf2-1d7e-4709-804f-5a99364837ea
    `external_group_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_group_id',
    -- column_id: 7e52179e-de07-41b8-bdf4-393fb72d4a67
    `previous_owner_id` BIGINT NULL COMMENT 'Fineract source column previous_owner_id',
    -- column_id: 6db8ba0c-646e-4aaf-a528-93b7afcfae4d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
