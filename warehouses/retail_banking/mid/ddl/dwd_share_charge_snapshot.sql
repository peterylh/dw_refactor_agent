-- DWD generated from m_share_account_charge
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_charge_snapshot;
-- table_id: 5530b695-0538-4066-9d50-8996347183d3
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_charge_snapshot (
    -- column_id: e12f7436-577e-4150-901e-711630cd12fc
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e12c371d-3096-464d-a2d3-a40191f9e2a8
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: a2c328fd-d1bc-4780-b893-23e2382e5fc1
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: b038a775-2991-49d6-aac2-9050450a08ee
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: d8319927-2e63-40fd-99a0-9c2a5de53d22
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: 993e5330-1a03-4466-a8e7-91c33a49ad6d
    `charge_payment_mode_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: a7913748-61d4-4914-be81-45fb57a78cc2
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: f1c552c1-f590-408d-a6f9-1b5d3a1f3542
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: ef6f331f-1ed7-400f-a80d-d8b24736244d
    `charge_amount_or_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column charge_amount_or_percentage',
    -- column_id: cac23e31-87cf-493d-b2a5-b4aafeb728b9
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 23ecb0ec-056f-41d8-b386-3b50fd5aa94a
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 2fedc715-f84f-4067-a1d9-dae2967941cb
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: 0c2bf999-348c-4337-aad7-58a399ceea4b
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 51e7a2aa-3857-4448-a1f9-e4da7a221dd8
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: ba763f4d-6801-4c80-9ac5-e012c74e16f8
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 596301df-c78c-4a81-aa07-9bbbcf5a1623
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: a502840e-5f13-4a61-bac3-f86c2c1fb12b
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: ecd3f55a-fcbb-4a40-ac8d-86692b82ac20
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: d0d68522-2ff2-4fcd-b05a-7dcf4528beff
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: b894ac58-3aaf-4e5b-8a3e-0238c4a89021
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
