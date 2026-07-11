-- ODS mirror of Apache Fineract m_provision_category (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_provision_category;
-- table_id: f9971162-fb66-483b-b5eb-74044328713f
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_provision_category (
    -- column_id: 0ef2779e-5e24-4339-8610-c197dd38c683
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f74cb1e5-0d96-45b1-9318-b73257cb7781
    `category_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column category_name',
    -- column_id: 909246d0-4401-4371-bffa-bb5832623323
    `description` VARCHAR(300) NULL COMMENT 'Fineract source column description',
    -- column_id: faae5170-13f0-49d9-a49e-0dc411f58546
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
