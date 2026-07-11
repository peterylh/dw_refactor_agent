-- ODS mirror of Apache Fineract m_payment_type (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_payment_type;
-- table_id: daf44da4-dfa7-4d75-8acb-4438c65b2033
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_payment_type (
    -- column_id: 02cd9f44-7a9e-4e5b-89ad-f7e673152769
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a327bc7a-467c-4b30-8552-f9a761ed83d0
    `value` VARCHAR(100) NULL COMMENT 'Fineract source column value',
    -- column_id: 41bb98b8-35d7-42f0-9e4e-eb59932be900
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 7bfa8f2e-f489-449e-a019-a879de68c757
    `is_cash_payment` BOOLEAN NULL COMMENT 'Fineract source column is_cash_payment',
    -- column_id: ed76bce5-fa0e-4acb-8870-caf373562b44
    `order_position` INT NOT NULL COMMENT 'Fineract source column order_position',
    -- column_id: 3ec5a0e2-dd26-4e01-ade8-cbc066aa69fb
    `code_name` VARCHAR(100) NULL COMMENT 'Fineract source column code_name',
    -- column_id: 2e173aa0-69f0-4ca8-a5f7-b7791436265c
    `is_system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column is_system_defined',
    -- column_id: 9bf3f4c9-9b4f-4cda-8822-802befe63d6e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
