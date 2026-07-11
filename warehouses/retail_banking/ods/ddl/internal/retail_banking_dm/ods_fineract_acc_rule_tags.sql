-- ODS mirror of Apache Fineract acc_rule_tags (总账与财务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_acc_rule_tags;
-- table_id: 6b585cb8-db3f-44a3-840c-da2b3dba662d
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_acc_rule_tags (
    -- column_id: 00d2c5a5-0629-4d34-87af-0d6fbf84889f
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 3c86a3e6-6cc2-4efb-bb4b-3959016b4e97
    `acc_rule_id` BIGINT NOT NULL COMMENT 'Fineract source column acc_rule_id',
    -- column_id: aa469caa-c103-404b-8913-d935269ef9ec
    `tag_id` INT NOT NULL COMMENT 'Fineract source column tag_id',
    -- column_id: af66f233-0591-4cd3-8df9-a9673de9b5dc
    `acc_type_enum` SMALLINT NOT NULL COMMENT 'Fineract source column acc_type_enum',
    -- column_id: 2c44f555-20ad-46b3-8ae9-66c7d4334a88
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
