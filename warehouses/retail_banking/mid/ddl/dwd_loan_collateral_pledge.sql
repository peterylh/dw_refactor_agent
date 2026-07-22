SET allow_partition_column_nullable = true;

-- DWD generated from m_loan_collateral_management
DROP TABLE IF EXISTS retail_banking_dm.dwd_loan_collateral_pledge;
-- table_id: 06e7695c-0473-4366-b3de-598b47789c54
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_loan_collateral_pledge (
    -- column_id: fcbbd5fb-45ed-4206-b04a-fa8200e7e9c1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: c9e8ce0e-69d5-4587-b261-64da74749601
    `business_date` DATE NULL COMMENT 'Standardized business date from the semantic spec',
    -- column_id: b34ef75e-433c-4718-839b-3063eda61cf3
    `quantity` DECIMAL(20,5) NOT NULL COMMENT 'Fineract source column quantity',
    -- column_id: a6652e5b-7bd6-4666-97e7-f16e512941e5
    `loan_id` BIGINT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: 3d762f17-1e8c-41a4-bb0c-7e727cb24a20
    `client_collateral_id` BIGINT NULL COMMENT 'Fineract source column client_collateral_id',
    -- column_id: 5082d4d3-b25d-4290-8a21-856d3503343a
    `is_released` BOOLEAN NULL COMMENT 'Fineract source column is_released',
    -- column_id: 39a447cc-09f5-4b56-893f-70887f6ce034
    `transaction_id` BIGINT NULL COMMENT 'Fineract source column transaction_id',
    -- column_id: fd6c0642-9814-458d-aedb-2bd4f05516ea
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`, `business_date`)
AUTO PARTITION BY LIST (`business_date`) ()
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
