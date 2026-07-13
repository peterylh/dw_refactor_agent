-- ODS mirror of Apache Fineract m_cashiers (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_cashiers;
-- table_id: b426a99b-4f76-44dd-805f-0686626d0851
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_cashiers (
    -- column_id: 337b26b6-b13b-4f2c-8d61-8fc7938e2636
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c9de4db2-8bd3-404b-a7a9-4a4be2196258
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 036cba16-e5e1-4247-9a58-0a538771ef20
    `teller_id` BIGINT NULL COMMENT 'Fineract source column teller_id',
    -- column_id: 064ea1ce-27c3-42b0-8e26-07174602735d
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: 8f647251-999c-4327-9f0c-5d58869a7a6f
    `start_date` DATE NULL COMMENT 'Fineract source column start_date',
    -- column_id: 8a90c68d-eede-4e22-b3c5-73a6a0656cf0
    `end_date` DATE NULL COMMENT 'Fineract source column end_date',
    -- column_id: 90e28f57-80ed-462d-ac1c-c963461ceb7f
    `start_time` VARCHAR(10) NULL COMMENT 'Fineract source column start_time',
    -- column_id: 71a11fb8-3d87-42a1-8e6c-595c910364c8
    `end_time` VARCHAR(10) NULL COMMENT 'Fineract source column end_time',
    -- column_id: 222cbaad-0935-479d-8e08-b4955426d633
    `full_day` BOOLEAN NULL COMMENT 'Fineract source column full_day',
    -- column_id: 41b2854d-1a6b-45b7-996e-c78700aea3cf
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
