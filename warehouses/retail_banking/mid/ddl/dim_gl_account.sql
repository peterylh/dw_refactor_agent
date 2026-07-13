-- DIM generated from acc_gl_account
DROP TABLE IF EXISTS retail_banking_dm.dim_gl_account;
-- table_id: 4bf2821c-b046-416b-92a7-a66734eca12a
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_gl_account (
    -- column_id: 52b13b3c-9d63-4b58-a03b-8984becfe9f5
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5125e5f7-2dfa-4a45-8a7b-dd7d27fed74d
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: b2ebaf9f-7bba-40ce-a623-06fb2c65b57f
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: 16960ebf-619d-4d74-965d-a1cd7a26c42a
    `hierarchy` VARCHAR(50) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: e5889658-2527-42d3-9caf-44fa7f106546
    `gl_code` VARCHAR(45) NOT NULL COMMENT 'Fineract source column gl_code',
    -- column_id: 51f4be46-76d4-47f3-be2c-b54660b4665e
    `disabled` BOOLEAN NOT NULL COMMENT 'Fineract source column disabled',
    -- column_id: e2ff11db-4b4f-4c57-a2c5-cad5d1e404c7
    `manual_journal_entries_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_journal_entries_allowed',
    -- column_id: b6acfca6-d512-40c4-b5f9-93004d84ed43
    `account_usage` TINYINT NOT NULL COMMENT 'Fineract source column account_usage',
    -- column_id: 07a1a899-31bd-4738-9b66-a63ff82f5819
    `classification_enum` SMALLINT NOT NULL COMMENT 'Fineract source column classification_enum',
    -- column_id: 792abafc-a360-4aab-9f27-d7bf474eb204
    `tag_id` INT NULL COMMENT 'Fineract source column tag_id',
    -- column_id: 277d5fdc-c0ca-44a2-a574-4f683118e2d2
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: 50ab630f-6d05-4296-826f-693b083de7c1
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
