-- ODS mirror of Apache Fineract m_share_account_transactions (投资、份额与资产持有)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_share_account_transactions;
-- table_id: 779c84ea-a616-4ee9-a917-3f73f7cf20af
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_share_account_transactions (
    -- column_id: 89a55806-b353-46fd-90f9-c3edaa5d903b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 59ba98a5-dc7d-49ab-9629-f28b70770f59
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: bbc8df2b-6cea-4027-98d6-74a9f08a3cc2
    `transaction_date` DATE NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 4fef6d95-1f41-4f85-bc92-b7181f9387e9
    `total_shares` BIGINT NULL COMMENT 'Fineract source column total_shares',
    -- column_id: 21bb7dbf-fbc3-4109-b580-faaa470cc039
    `unit_price` DECIMAL(10,2) NULL COMMENT 'Fineract source column unit_price',
    -- column_id: 026c5d4f-18c4-47be-b216-e5e7e51e8bef
    `amount` DECIMAL(20,2) NULL COMMENT 'Fineract source column amount',
    -- column_id: 42fd1c93-0f55-4af3-9a34-5176c00864b1
    `charge_amount` DECIMAL(20,2) NULL COMMENT 'Fineract source column charge_amount',
    -- column_id: 94f6d233-2d95-46d6-832f-10511704f3e0
    `amount_paid` DECIMAL(20,2) NULL COMMENT 'Fineract source column amount_paid',
    -- column_id: f37ed31b-9eb9-45ce-925d-dcf3bd34fc77
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: a774229f-5f7f-46a4-996a-f506fbd0ca67
    `type_enum` SMALLINT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: 27f19dec-8525-4d49-97d5-80f56e9af59c
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 55ad781f-cf67-43d2-9f58-0965968faa76
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
