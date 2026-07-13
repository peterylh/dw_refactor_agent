-- ODS mirror of Apache Fineract m_share_account_charge (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_account_charge;
-- table_id: 8d14ed06-9442-4481-b166-e576f1249039
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_account_charge (
    -- column_id: 87056306-2725-4641-9466-de3a1e57b2b7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 85880613-5312-4352-be11-efe21df43ed5
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: aa6300d3-fa73-4d2a-bf3e-444d15c8e40e
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 44679e5b-755a-45a2-b42e-96ebc72c3e91
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 53d285e7-db25-4ece-8225-7fa6221a0c4a
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: ce84fe5c-ad85-40ae-8337-04749101557c
    `charge_payment_mode_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: adcd70df-68bb-4a6b-a5b5-c34460145403
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: 09431db0-41e6-4edb-aa45-6b0ac7596395
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: 4525da6a-6bc9-4ba0-91be-ff1f3e66bb9e
    `charge_amount_or_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column charge_amount_or_percentage',
    -- column_id: ea6e9746-eb6e-4ac1-986c-259c21ae01d2
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: ad921f88-40b0-49bd-9e47-10a5f790295d
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 890506d0-0ea0-4ff2-8c14-22d46f3fd30f
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: 224285b2-0b23-4bc9-a947-e751d9925c84
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: c4dcde87-d027-4a9f-b18d-cae0b4ba4af3
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: 14882796-eb5d-461c-bf1d-e3aecf15c21e
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 86db1343-1343-4141-b3bf-6f229256beba
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: dc070a64-c9ae-4240-a0ac-d17be4a2bb7f
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: df339052-3c20-4fb4-b0db-c3c03db186ac
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: 0d7c51cd-efce-400d-b637-e35a448e9d3e
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 8c036631-c044-4a3e-8090-b904cf5b3509
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
