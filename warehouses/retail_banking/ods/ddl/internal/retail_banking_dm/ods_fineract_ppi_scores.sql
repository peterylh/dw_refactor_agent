-- ODS mirror of Apache Fineract ppi_scores (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_ppi_scores;
-- table_id: ed748703-2053-4e73-b3d0-cb8932cacb10
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_ppi_scores (
    -- column_id: 35832721-d447-451e-b8bf-85842340bb49
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: db34f8d1-33fb-40d8-84fb-4d1e7918ac98
    `score_from` INT NOT NULL COMMENT 'Fineract source column score_from',
    -- column_id: 3e803afa-ce72-4276-82df-d88fa78c8eac
    `score_to` INT NOT NULL COMMENT 'Fineract source column score_to',
    -- column_id: 77b70729-eb1f-4f13-bb3d-efb445085efd
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
