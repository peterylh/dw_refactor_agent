SET allow_partition_column_nullable = true;

-- DWD generated from m_client_charge
DROP TABLE IF EXISTS retail_banking_dm.dwd_client_charge;
-- table_id: 4145e6c6-ac11-40f3-89fa-ad6a75aa3d8d
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_client_charge (
    -- column_id: 4891d8cb-a1b1-473e-ab26-321d54273d4f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e4a45db8-ae7a-4bfb-a46e-d00c7acb9879
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: c80fae21-6ab7-4214-a5f8-bad169e06a79
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 58296c98-05d3-468c-b8a4-e9497e415bcb
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: fe623012-08ee-47b6-9f71-ddb9a7251957
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 14eb9958-8af2-4f4d-a3d4-1553b74c1669
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: edac09e1-9f23-4e8b-8cc4-07bcf051b5e0
    `charge_due_date` DATE NULL COMMENT 'Fineract source column charge_due_date',
    -- column_id: 0c0c206e-79a8-477f-8df8-5b75455efef9
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: 826f1261-765f-44c0-95d9-4ace77446d9d
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: bfb34117-d299-475f-9840-852ebc10c038
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 423e1d85-d615-422c-aba8-0421d5ea59c0
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: 34cbde2b-ce27-4f4e-8e16-f2b0c4628e73
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: 9a324ce4-c320-413b-8bda-bb2d71aba171
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: 8b507bb1-f687-4e33-9e2b-950f5639f8eb
    `is_paid_derived` BOOLEAN NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: b662a14c-1c9a-4b45-a886-74e25c659b5e
    `waived` BOOLEAN NULL COMMENT 'Fineract source column waived',
    -- column_id: fa200685-b448-4970-b802-2f5b671ac023
    `is_active` BOOLEAN NULL COMMENT 'Fineract source column is_active',
    -- column_id: 63fa75f6-6215-42b1-9ba9-cdd9d88dd6b6
    `inactivated_on_date` DATE NULL COMMENT 'Fineract source column inactivated_on_date',
    -- column_id: 140363af-f316-40c8-9e01-a5cbe881d181
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
