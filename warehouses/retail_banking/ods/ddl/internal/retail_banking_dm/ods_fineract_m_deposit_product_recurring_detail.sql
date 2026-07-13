-- ODS mirror of Apache Fineract m_deposit_product_recurring_detail (存款与储蓄)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_deposit_product_recurring_detail;
-- table_id: cf55c84f-976a-4920-b0b2-95cda4d6032b
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_deposit_product_recurring_detail (
    -- column_id: 932ab5fc-5180-4cfd-b3d0-d590ec70e460
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 1788683e-61d8-4d17-a1a4-14cb426e9ccd
    `savings_product_id` BIGINT NOT NULL COMMENT 'Fineract source column savings_product_id',
    -- column_id: 8ff741f3-6e47-4ca4-a8fa-810b17996a09
    `is_mandatory` BOOLEAN NOT NULL COMMENT 'Fineract source column is_mandatory',
    -- column_id: 73ab3e50-fe53-4ecb-8177-f4f3c831d9d3
    `allow_withdrawal` BOOLEAN NOT NULL COMMENT 'Fineract source column allow_withdrawal',
    -- column_id: b427ccbd-7bd0-48a4-90b1-7fc62cae9a62
    `adjust_advance_towards_future_payments` BOOLEAN NOT NULL COMMENT 'Fineract source column adjust_advance_towards_future_payments',
    -- column_id: 5428ce99-6e97-4054-9fa0-f641ff0fbc49
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
