-- ODS mirror of Apache Fineract m_entity_datatable_check (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_entity_datatable_check;
-- table_id: dc04cc1e-0d84-47d6-a0e6-e535a6d4b3a9
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_entity_datatable_check (
    -- column_id: 5efaf7d9-0c34-4462-ab07-ef839e825b7a
    `id` INT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f2731c83-4625-401f-ba93-02b181561ef7
    `application_table_name` VARCHAR(200) NOT NULL COMMENT 'Fineract source column application_table_name',
    -- column_id: 14557c4c-f32c-43c7-869f-24c326c71382
    `x_registered_table_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column x_registered_table_name',
    -- column_id: 9d2268c9-91ae-4263-a443-d2dc41337d3f
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: c473ae92-ee63-48c3-912e-aae12da45ff1
    `system_defined` BOOLEAN NOT NULL COMMENT 'Fineract source column system_defined',
    -- column_id: 944d4c38-4a27-4b15-8995-285c6d7261ba
    `product_id` BIGINT NULL COMMENT 'Fineract source column product_id',
    -- column_id: 88b48a17-9061-4c4e-aaac-98db6503b50a
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
