-- ODS mirror of Apache Fineract m_provisioning_criteria_definition (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_provisioning_criteria_definition;
-- table_id: 681a8c64-7cc4-40db-9c65-97fe6d53ced8
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_provisioning_criteria_definition (
    -- column_id: a9043997-284d-4c3e-921d-51341c16b6f6
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9d73375f-d0ca-4d07-bfc4-324cc48acddb
    `criteria_id` BIGINT NOT NULL COMMENT 'Fineract source column criteria_id',
    -- column_id: c5fd629d-7718-408b-90c8-60993ddf24b9
    `category_id` BIGINT NOT NULL COMMENT 'Fineract source column category_id',
    -- column_id: 75a60bcb-8588-4a5f-b8bc-474e9fe01001
    `min_age` BIGINT NOT NULL COMMENT 'Fineract source column min_age',
    -- column_id: 733a0e57-03cd-4598-905f-2304bfb043ad
    `max_age` BIGINT NOT NULL COMMENT 'Fineract source column max_age',
    -- column_id: 612d8d60-a207-4b1b-9196-cc604798ee2e
    `provision_percentage` DECIMAL(5,2) NOT NULL COMMENT 'Fineract source column provision_percentage',
    -- column_id: 435555cc-a5f3-4479-852f-cff49be45fa1
    `liability_account` BIGINT NULL COMMENT 'Fineract source column liability_account',
    -- column_id: f19de6f5-8bf9-4f22-9ea9-f8bac9451bf4
    `expense_account` BIGINT NULL COMMENT 'Fineract source column expense_account',
    -- column_id: 6074a710-64f9-49dd-b2d4-6a23b1295300
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
