-- DWD generated from m_share_account_charge_paid_by
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_charge_allocation;
-- table_id: b4063afa-11e7-4691-90db-8175099357f4
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_charge_allocation (
    -- column_id: 2019c2a9-2d1f-46c9-8fee-075ef473e690
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c9d04a2e-0859-426a-8306-7b3d16e5270a
    `share_transaction_id` BIGINT NULL COMMENT 'Fineract source column share_transaction_id',
    -- column_id: 36e78f25-7f2a-40f7-b367-0c47cfc8b8e9
    `charge_transaction_id` BIGINT NULL COMMENT 'Fineract source column charge_transaction_id',
    -- column_id: e9b20574-3cbd-46d5-bffd-7b05b1236526
    `amount` DECIMAL(20,2) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 61e72e4d-0f14-46dc-bb4d-02a5f397f288
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: 26720456-cd24-41ed-a408-4887d5fad280
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
