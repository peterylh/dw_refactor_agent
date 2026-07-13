-- ODS mirror of Apache Fineract m_client_charge (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client_charge;
-- table_id: 37592c85-393c-4a90-8ef7-a8a27fa7050f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client_charge (
    -- column_id: 37d79ce1-3608-4553-a513-9bf1e8c813f1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9b203abd-95ba-407b-a08c-f7f4354adca4
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 03d5fe0e-ba63-4a79-a734-a87664a30824
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: bc968013-1dfd-4882-813d-f8ca29d5481a
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 643e5b86-73c6-475b-af81-c7fee15d867f
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 05fc3f73-8552-406e-8bc2-69dde32acd11
    `charge_due_date` DATE NULL COMMENT 'Fineract source column charge_due_date',
    -- column_id: 3215295b-12ba-4134-99c7-8b798f5aa0e7
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: 10ba52da-16d0-440f-987d-718b574a497c
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 64f95ed8-d56b-4139-b3dc-4b2e4785464c
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 145b34c3-505b-499b-ba5f-4ab268b38608
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: cbc1665d-9a27-48c5-8b5b-cd261e86a259
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: f3be875c-15e9-4e41-87a4-e9c9dd96dbc2
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: e37103a2-4e28-48e1-90ca-579da00c1f97
    `is_paid_derived` BOOLEAN NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: be476da9-9ca4-444a-aa20-9a7842df8b9b
    `waived` BOOLEAN NULL COMMENT 'Fineract source column waived',
    -- column_id: 30d7047b-7da5-4d0f-8fb7-0e673a804113
    `is_active` BOOLEAN NULL COMMENT 'Fineract source column is_active',
    -- column_id: 69c14481-bc3a-44c4-a56e-525e436f250b
    `inactivated_on_date` DATE NULL COMMENT 'Fineract source column inactivated_on_date',
    -- column_id: ff830e09-20aa-4a46-befa-26f5fceb9b48
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
