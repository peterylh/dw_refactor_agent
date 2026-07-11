-- ODS mirror of Apache Fineract m_business_date (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_business_date;
-- table_id: 64053e77-8605-4e52-b55a-a03f75a16733
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_business_date (
    -- column_id: 08e82019-a312-47df-81c9-0c4e8b2b6ba0
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fcddaf29-6fa6-4569-85d0-900d214790f3
    `type` VARCHAR(100) NOT NULL COMMENT 'Fineract source column type',
    -- column_id: 2d703dde-046d-4d25-875e-a35a3430054a
    `date` DATE NOT NULL COMMENT 'Fineract source column date',
    -- column_id: 0aef4fab-db12-483a-a65f-d8cd91ddc1cf
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e43a874b-0a6e-4184-bf3b-dc159b21ec2b
    `created_date` DATETIME NULL COMMENT 'Fineract source column created_date',
    -- column_id: 08cbcb59-3288-433e-a630-7bbb68849b32
    `version` BIGINT NOT NULL COMMENT 'Fineract source column version',
    -- column_id: 347eecb1-abbe-47af-90ed-0f86f649767f
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: eccfdc2f-f7d9-41af-a93f-74046080f0e6
    `lastmodified_date` DATETIME NULL COMMENT 'Fineract source column lastmodified_date',
    -- column_id: 085c5ee9-4a38-44ad-a1b9-45911a55e368
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 8441dd24-ab7d-4b34-ad79-86dddcb8434d
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: bc0e86ec-d634-41cc-9834-bd2c08e8b65a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
