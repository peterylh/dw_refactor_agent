-- DIM generated from m_holiday
DROP TABLE IF EXISTS retail_banking_dm.dim_holiday;
-- table_id: ad883fcb-6a9f-4e69-84c9-20a56d97da4c
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_holiday (
    -- column_id: 0b9497d6-64be-4fff-aee8-30e48a787cb9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e128f38e-33a7-459d-a5d0-48f24f3bb70e
    `name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 4cfaf77f-a561-43cf-9d76-658deeb3b4d3
    `from_date` DATE NOT NULL COMMENT 'Fineract source column from_date',
    -- column_id: b9ccc633-312e-4762-9da9-725ae07a2335
    `to_date` DATE NOT NULL COMMENT 'Fineract source column to_date',
    -- column_id: a40d394e-2d70-42a6-b672-602b7150c6f8
    `repayments_rescheduled_to` DATE NULL COMMENT 'Fineract source column repayments_rescheduled_to',
    -- column_id: 79c435d1-7c62-44ed-99d5-bf0d14846ad5
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 27e118dc-6e0a-46e8-833e-c89a448cf703
    `processed` BOOLEAN NOT NULL COMMENT 'Fineract source column processed',
    -- column_id: 00a356ac-5ab9-4900-b6bc-186d53eb1f2e
    `description` VARCHAR(100) NULL COMMENT 'Fineract source column description',
    -- column_id: e410529c-505c-4792-869d-c57f36602484
    `rescheduling_type` INT NOT NULL COMMENT 'Fineract source column rescheduling_type',
    -- column_id: 3f0c3b50-8214-4989-b1f8-57c79f279da9
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
