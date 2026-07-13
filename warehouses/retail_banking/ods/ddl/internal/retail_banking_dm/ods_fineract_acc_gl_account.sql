-- ODS mirror of Apache Fineract acc_gl_account (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_gl_account;
-- table_id: e4050643-0099-460c-84fe-c05a230d5fb5
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_gl_account (
    -- column_id: 71e0a87f-9e52-4b10-9594-6ca80884e4fd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: d8462caa-927d-49bb-98d5-2fc1afdf9bb5
    `name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: ae742514-8713-4cc0-9a72-00a7297ee89e
    `parent_id` BIGINT NULL COMMENT 'Fineract source column parent_id',
    -- column_id: af49dbc1-dd5f-4462-a9c2-b70a3e053953
    `hierarchy` VARCHAR(50) NULL COMMENT 'Fineract source column hierarchy',
    -- column_id: 982c372a-4f4f-47d7-95b4-317c1134e6cd
    `gl_code` VARCHAR(45) NOT NULL COMMENT 'Fineract source column gl_code',
    -- column_id: 360bd710-515b-41cf-a829-db7db07ae949
    `disabled` BOOLEAN NOT NULL COMMENT 'Fineract source column disabled',
    -- column_id: 5a34703f-263a-4795-8554-f777da4de3f7
    `manual_journal_entries_allowed` BOOLEAN NOT NULL COMMENT 'Fineract source column manual_journal_entries_allowed',
    -- column_id: 51c11a7c-b850-4ad5-9db1-5a4b0c81df86
    `account_usage` TINYINT NOT NULL COMMENT 'Fineract source column account_usage',
    -- column_id: 1f801e66-daf8-44bd-9d12-eb636fef9e60
    `classification_enum` SMALLINT NOT NULL COMMENT 'Fineract source column classification_enum',
    -- column_id: 0621d9c5-82da-4ed8-b2d0-dfff46547bcd
    `tag_id` INT NULL COMMENT 'Fineract source column tag_id',
    -- column_id: 66b16a0e-a6ed-4e3f-9522-7e4e675b7704
    `description` VARCHAR(500) NULL COMMENT 'Fineract source column description',
    -- column_id: ce18e8e9-cf89-4ac9-ab59-9ea2016b576c
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
