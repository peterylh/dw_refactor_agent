SET allow_partition_column_nullable = true;

-- DWD generated from m_office_transaction
DROP TABLE IF EXISTS retail_banking_dm.dwd_office_cash_transfer;
-- table_id: 167bffec-ebda-4af2-bcd4-b9cbe6483fd4
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_office_cash_transfer (
    -- column_id: 473001d2-fe9d-4a86-b804-ea3fc3c956ae
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b17a27f6-411f-40b1-96cb-5308fc1e5d86
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 90af3235-1925-4034-a1a8-9644801b8598
    `from_office_id` BIGINT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 552c111f-f21b-49a9-91e5-2c6a2331b7ec
    `to_office_id` BIGINT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: cf6cdb15-ded8-45a9-9ebf-4afb034f703e
    `currency_code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column currency_code',
    -- column_id: b3083dfb-8794-4064-9cd0-437872d05014
    `currency_digits` INT NOT NULL COMMENT 'Fineract source column currency_digits',
    -- column_id: e4eff1a1-3cad-46ec-8369-396b47a14243
    `transaction_amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column transaction_amount',
    -- column_id: ec055be7-b47c-42e1-8eaf-4695152426d9
    `transaction_date` DATE NOT NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 48f2bbb6-eee7-49b1-aa26-8699e6ce5cc0
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 1a685640-749f-47fc-8c87-95f08cbc83ba
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
