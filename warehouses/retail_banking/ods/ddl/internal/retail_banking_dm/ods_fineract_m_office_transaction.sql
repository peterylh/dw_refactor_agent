-- ODS mirror of Apache Fineract m_office_transaction (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_office_transaction;
-- table_id: fdc3dcc6-d355-4c17-9b12-d3fd188bf1aa
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_office_transaction (
    -- column_id: ecc73134-ca26-4934-9825-cb59a2610de8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 0fe5d0d3-67ce-48cd-bc77-91b306a16cc2
    `from_office_id` BIGINT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 7b42ee56-2f95-4fd1-92d8-ea6e316995af
    `to_office_id` BIGINT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: a084c2d5-f6c7-4b43-a91b-cc3d26aa0d8d
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: 464c6290-9bca-4481-80e6-3f7f9dad3095
    `currency_digits` INT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: 378da515-8dc5-4b69-99f7-887dde48d9b1
    `transaction_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column transaction_amount',
    -- column_id: 14b5cc0a-35d1-42cc-ba6c-e2eba18f5914
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 58524d7c-2e5c-4325-9215-f96af2104818
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 21163485-5620-43d1-9561-b9eab22f96c3
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
