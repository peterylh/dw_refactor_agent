-- DIM generated from m_provision_category
DROP TABLE IF EXISTS retail_banking_dm.dim_provision_category;
-- table_id: 37c6ba7b-a3af-4470-8eaf-49923c76fceb
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_provision_category (
    -- column_id: fbfedf5b-974e-40bc-8884-7f328be104c7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: b514399f-6ec3-4cc2-a5af-530be78e47a3
    `category_name` VARCHAR(100) NOT NULL COMMENT 'Fineract source column category_name',
    -- column_id: 3d17d311-2f34-4951-91b8-d9cc1a7b7333
    `description` VARCHAR(300) NULL COMMENT 'Fineract source column description',
    -- column_id: ad1b81e4-170c-4c96-879e-5fad8bc486db
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
