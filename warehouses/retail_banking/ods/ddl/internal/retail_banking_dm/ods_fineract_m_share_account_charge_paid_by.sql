-- ODS mirror of Apache Fineract m_share_account_charge_paid_by (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_account_charge_paid_by;
-- table_id: 6e446179-dd47-4a85-9738-cd055496883d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_account_charge_paid_by (
    -- column_id: fd107760-a991-4937-a4bf-8274cf6800b2
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 05895bc6-5fe5-4160-ab23-ed356a037518
    `share_transaction_id` BIGINT NULL COMMENT 'Fineract source column share_transaction_id',
    -- column_id: 3df2bfde-592b-49aa-9047-ad603b45ea92
    `charge_transaction_id` BIGINT NULL COMMENT 'Fineract source column charge_transaction_id',
    -- column_id: 790373ae-7855-4fab-a2d2-e4f7232bc230
    `amount` DECIMAL(20,2) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 30d49552-e2ec-48a9-a499-110d100f1c83
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
