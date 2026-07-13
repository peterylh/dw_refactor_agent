-- ODS mirror of Apache Fineract ppi_likelihoods_ppi (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_ppi_likelihoods_ppi;
-- table_id: 3f17ad2f-e1df-43c6-b9e9-f1e21eaeeebe
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_ppi_likelihoods_ppi (
    -- column_id: edc546a7-8e87-45a0-96ba-cf7d05e95d46
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e9eb5d9c-7d64-4251-b25e-53d5894131ce
    `likelihood_id` BIGINT NOT NULL COMMENT 'Fineract source column likelihood_id',
    -- column_id: 46d7079e-6e7a-4343-b9dc-a0606420e3a4
    `ppi_name` VARCHAR(250) NOT NULL COMMENT 'Fineract source column ppi_name',
    -- column_id: 71da2c57-8235-4e4a-8be9-724737e2662c
    `enabled` INT NOT NULL COMMENT 'Fineract source column enabled',
    -- column_id: 3207e6bf-46af-40f0-a15e-d3a8c5343bc9
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
