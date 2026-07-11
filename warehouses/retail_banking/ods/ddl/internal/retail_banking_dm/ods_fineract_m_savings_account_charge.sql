-- ODS mirror of Apache Fineract m_savings_account_charge (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_savings_account_charge;
-- table_id: 58978802-489e-4de1-8399-df08935b09cf
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_savings_account_charge (
    -- column_id: 466c6b46-816b-4a13-ae30-b7d321bac2c8
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 73fc0318-8784-4846-b24b-a99e4d06e97a
    `savings_account_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_account_id',
    -- column_id: 8f528852-c1af-4226-9664-53e039e9ce5c
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 63737297-dd46-41f8-b20a-0e5842984b43
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 5bd46496-0045-42f6-bc89-b96a27d4188f
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: 72672ca6-ee92-4f3b-8428-81c6fb3d7b79
    `charge_due_date` DATE NULL COMMENT 'Fineract source column charge_due_date',
    -- column_id: 6bb2d707-879e-4ce5-9363-172b766292fd
    `fee_on_month` SMALLINT NULL COMMENT 'Fineract source column fee_on_month',
    -- column_id: f395fe7e-fbd5-4cd4-be5b-ad568d8ad069
    `fee_on_day` SMALLINT NULL COMMENT 'Fineract source column fee_on_day',
    -- column_id: a7b9200f-457b-4e67-bd55-0eacac99c0be
    `fee_interval` SMALLINT NULL COMMENT 'Fineract source column fee_interval',
    -- column_id: eb899f59-ad68-4fff-928a-8b77633bbd92
    `free_withdrawal_count` INT NULL COMMENT 'Fineract source column free_withdrawal_count',
    -- column_id: 33fa2498-31d2-4ba2-bcd0-42397293bbb2
    `charge_reset_date` DATE NULL COMMENT 'Fineract source column charge_reset_date',
    -- column_id: 79ba6748-bf7c-4727-8a51-726d940b15c5
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: a314c1df-cf13-4588-9dd7-5890d137bc34
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: c34a4d92-270c-4e55-abd9-12478050eb6c
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: 633abf3c-ee62-47cd-8984-d59b933affd8
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 27219dd8-7993-45d4-a826-7bac3e200ef9
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 9b13bb92-1911-428f-9376-35b179de5ea2
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: e66946e0-4090-4e58-8e53-c27e433466f3
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 59e3f150-b145-48d8-b3b7-0a4a68f2b7d3
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: e0802413-88e9-42c6-bfa9-a713c7f3cfe1
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 27b59bde-adf4-4654-93e4-4aec6746b4b4
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: 5664a652-efba-4977-a2a5-e3d7b80b4c14
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: aeee5179-abb3-4903-a5c4-88a1f30bffa5
    `inactivated_on_date` DATE NULL COMMENT 'Fineract source column inactivated_on_date',
    -- column_id: 5f378efa-a2b1-417c-a38a-8376c1f8ba0c
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 7ac33eeb-9fe7-4e1f-b803-2c75edde4398
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 8390a183-2290-4a6a-8cf5-be04f3369999
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 1810a900-7b73-45d3-b556-bd79a447715c
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 56aec013-4ac0-40e9-8bec-499caf6e470a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
