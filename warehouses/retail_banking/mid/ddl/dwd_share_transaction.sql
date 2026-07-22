SET allow_partition_column_nullable = true;

-- DWD generated from m_share_account_transactions
DROP TABLE IF EXISTS retail_banking_dm.dwd_share_transaction;
-- table_id: ad61e944-2a5d-4ff5-a012-24a67e4711b6
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_share_transaction (
    -- column_id: 7c99eca5-b852-4fbb-be32-dc303394fb57
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 66658f99-7380-450a-ad24-2cb297a96ad1
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: f5e5a0d6-154d-43b3-aae8-7c5e7298a644
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: faf6f85d-d698-4fd7-b001-dfa3ad0c49af
    `transaction_date` DATE NULL COMMENT 'Fineract source column transaction_date',
    -- column_id: 48b3d94d-e932-4621-bd69-cbe5279387a9
    `total_shares` BIGINT NULL COMMENT 'Fineract source column total_shares',
    -- column_id: 2dd979a8-11b0-4734-b3be-3d34a7cad67d
    `unit_price` DECIMAL(10,2) NULL COMMENT 'Fineract source column unit_price',
    -- column_id: 302cbc44-e518-454f-9f74-d935670b77c0
    `amount` DECIMAL(20,2) NULL COMMENT 'Fineract source column amount',
    -- column_id: d085e043-be96-414f-9624-e344395ed57f
    `charge_amount` DECIMAL(20,2) NULL COMMENT 'Fineract source column charge_amount',
    -- column_id: 0d954ab8-1f9a-4154-99b9-36ef15b3180d
    `amount_paid` DECIMAL(20,2) NULL COMMENT 'Fineract source column amount_paid',
    -- column_id: 14e52d65-5979-4284-bd75-1ce3ee8d7c86
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: d38e5381-f603-4a99-a14f-9aef38b42421
    `type_enum` SMALLINT NULL COMMENT 'Fineract source column type_enum',
    -- column_id: 280ab528-72d3-4e70-be9c-83eea57b17ef
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: e07a8716-927c-4310-84ca-087925591231
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
