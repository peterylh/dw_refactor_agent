-- DIM generated from m_code_value
DROP TABLE IF EXISTS retail_banking_dm.dim_code_value;
-- table_id: e8514e6b-b0b8-4a1b-b4bc-1b884440c0cd
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_code_value (
    -- column_id: 97954beb-f385-4983-b4fc-bf13ab5c18f3
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e3f9e655-676d-423a-ae66-c55700c0b642
    `code_id` INT NOT NULL COMMENT 'Fineract source column code_id',
    -- column_id: 88b3a891-bdce-449e-a74f-ef91423b4189
    `code_value` VARCHAR(100) NULL COMMENT 'Fineract source column code_value',
    -- column_id: 8568a6a0-9ffd-4cdf-90a4-4805884e5ea1
    `code_description` VARCHAR(500) NULL COMMENT 'Fineract source column code_description',
    -- column_id: 038082c1-c19d-43e8-8877-276e72c75b3b
    `order_position` INT NOT NULL COMMENT 'Fineract source column order_position',
    -- column_id: 15800de9-ab9c-493f-95ea-82a5eed3969e
    `code_score` INT NULL COMMENT 'Fineract source column code_score',
    -- column_id: 6c239e96-722f-400e-9b3f-1a8f57e1dbe4
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 601d5e87-fe3f-434d-8eea-6e2237082be9
    `is_mandatory` BOOLEAN NOT NULL COMMENT 'Fineract source column is_mandatory',
    -- column_id: 23b9cfe5-30af-44aa-a8be-751afd5d2340
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
