-- ODS mirror of Apache Fineract acc_gl_financial_activity_account (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_gl_financial_activity_account;
-- table_id: 80a6537b-9ec9-4377-a6dc-ac318c8251ea
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_gl_financial_activity_account (
    -- column_id: d94da710-28b1-47fb-bcca-aeb5ff55461d
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: a1dcf634-ab58-421c-8ca5-7d3bd241a8ca
    `gl_account_id` BIGINT NOT NULL COMMENT 'Fineract source column gl_account_id',
    -- column_id: f919242f-6558-4b74-8fc5-39dfbaebfad4
    `financial_activity_type` SMALLINT NOT NULL COMMENT 'Fineract source column financial_activity_type',
    -- column_id: ba62f387-afc9-4efe-b3e6-413c76003229
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
