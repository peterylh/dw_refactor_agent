-- ODS mirror of Apache Fineract m_surveys (渠道与客户服务)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_surveys;
-- table_id: cbaee6e2-5a10-478f-8782-a71c6aaa6a41
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_surveys (
    -- column_id: 8481a738-2b32-4e27-915e-8fbdd2763177
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 5c951ff3-48c5-45de-aabf-0c6b75a00142
    `a_key` VARCHAR(32) NOT NULL COMMENT 'Fineract source column a_key',
    -- column_id: d2514298-3110-4409-a84b-c2b8dae3242a
    `a_name` VARCHAR(255) NOT NULL COMMENT 'Fineract source column a_name',
    -- column_id: 5660dd4b-c0b1-49a6-b927-9f285b8da81d
    `description` VARCHAR(4000) NULL COMMENT 'Fineract source column description',
    -- column_id: a23ab893-1e2c-41d5-96d0-46819af8509e
    `country_code` VARCHAR(2) NOT NULL COMMENT 'Fineract source column country_code',
    -- column_id: 5a08f8ee-fe4e-48e7-8612-e582f2d43570
    `valid_from` DATE NULL COMMENT 'Fineract source column valid_from',
    -- column_id: badbf82d-ea55-4db3-92e2-3009e82bf301
    `valid_to` DATE NULL COMMENT 'Fineract source column valid_to',
    -- column_id: 9e56ade1-ff3c-4a98-9085-8ad5f750742b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
