-- DIM generated from m_payment_type
DROP TABLE IF EXISTS retail_banking_dm.dim_payment_type;
-- table_id: 8aeec679-ee20-4349-8113-a0a3a023ec91
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_payment_type (
    -- column_id: 4297a46a-1ec3-4bbd-800c-6690bb6dcab2
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 32a6c4c0-24c3-44f2-ac7e-6af8a8427571
    `value` VARCHAR(100) NULL COMMENT 'Fineract source column value',
    -- column_id: 93911141-b72e-4151-9461-6253e022036d
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: b123f7e9-e5bc-4cff-b28a-84af4011ddf2
    `is_cash_payment` BOOLEAN NULL COMMENT 'Fineract source column is_cash_payment',
    -- column_id: 83723e4c-b694-4637-a2d2-58de592b55c5
    `order_position` INT NOT NULL COMMENT 'Fineract source column order_position',
    -- column_id: 6dbc8b58-cf84-4579-a1c6-9885f87970a4
    `code_name` VARCHAR(100) NULL COMMENT 'Fineract source column code_name',
    -- column_id: 249814a5-42f1-4ca1-a0a1-056dc2317201
    `is_system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column is_system_defined',
    -- column_id: 91aa8836-5f9e-4986-8f55-961d09837abc
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
