-- ODS mirror of Apache Fineract m_organisation_currency (产品、定价与税费)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_organisation_currency;
-- table_id: fff6ed92-f286-460f-8f95-e05b38dc6d78
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_organisation_currency (
    -- column_id: 28ce7383-6236-4618-af15-b1ca706e816b
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: fcae21ae-22c1-48bc-a4b6-d041219469c2
    `code` VARCHAR(3) NOT NULL COMMENT 'Fineract source column code',
    -- column_id: b2bfdfbb-f9e5-4bf2-ab55-1ba4b0d5eae8
    `decimal_places` SMALLINT NOT NULL COMMENT 'Fineract source column decimal_places',
    -- column_id: a8a02f7c-ddc3-48aa-9e8b-4860b707bbc6
    `currency_multiplesof` SMALLINT NULL COMMENT 'Fineract source column currency_multiplesof',
    -- column_id: dc2b6567-3774-46d0-a8fc-6d2848cc2ae1
    `name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column name',
    -- column_id: 5204c9b7-6f3a-49b8-afa9-4b9f072bf24a
    `display_symbol` VARCHAR(10) NULL COMMENT 'Fineract source column display_symbol',
    -- column_id: db742e8e-0673-4dfe-b59f-c0507507a26b
    `internationalized_name_code` VARCHAR(50) NOT NULL COMMENT 'Fineract source column internationalized_name_code',
    -- column_id: cf318ef2-6786-4a40-8f5e-1258ed093a4e
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
