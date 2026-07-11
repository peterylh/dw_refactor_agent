-- ODS mirror of Apache Fineract interop_identifier (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_interop_identifier;
-- table_id: 95e2ba5d-dfdf-454b-a612-c48930dd479d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_interop_identifier (
    -- column_id: 03090668-1997-4d11-85f4-19e23b5221fd
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e3706cae-a126-427c-8dbc-5492d02dd2e5
    `account_id` BIGINT NOT NULL COMMENT 'Fineract source column account_id',
    -- column_id: 89bd8688-c10a-4938-af68-8adcd65c6f44
    `type` VARCHAR(32) NOT NULL COMMENT 'Fineract source column type',
    -- column_id: b2c75eb9-7a18-4368-b0dd-86c49308464c
    `a_value` VARCHAR(128) NOT NULL COMMENT 'Fineract source column a_value',
    -- column_id: 85691e6b-523d-4dcc-b912-03ebcbd497f5
    `sub_value_or_type` VARCHAR(128) NULL COMMENT 'Fineract source column sub_value_or_type',
    -- column_id: 7a38b3ae-e24b-4786-b2af-c98aa4cfbe97
    `created_by` VARCHAR(32) NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 2e9a2aa3-2c88-4eb9-a1eb-898a1861c259
    `created_on` DATETIME NOT NULL COMMENT 'Fineract source column created_on',
    -- column_id: c8339529-0631-41ca-8380-1c93211edf7f
    `modified_by` VARCHAR(32) NULL COMMENT 'Fineract source column modified_by',
    -- column_id: 121942ff-dc74-4f63-98d5-9eda74a48163
    `modified_on` DATETIME NULL COMMENT 'Fineract source column modified_on',
    -- column_id: 4afb06a8-395f-4ceb-98ff-65928c970efd
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
