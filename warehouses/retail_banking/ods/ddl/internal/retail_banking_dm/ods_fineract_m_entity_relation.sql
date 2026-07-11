-- ODS mirror of Apache Fineract m_entity_relation (公共参考与元数据)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_entity_relation;
-- table_id: d7ddf3c8-0541-49c8-aefb-d3f474b56748
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_entity_relation (
    -- column_id: c3951d99-4e6d-4cdc-90ad-90650e53ee0a
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 9abb51a0-3dd5-4e9c-b383-067a724aa809
    `from_entity_type` INT NOT NULL COMMENT 'Fineract source column from_entity_type',
    -- column_id: 62ef5614-76c8-40b2-a366-f2e06dd820b3
    `to_entity_type` INT NOT NULL COMMENT 'Fineract source column to_entity_type',
    -- column_id: 1164be25-b347-4948-9319-a70efc75e66e
    `code_name` VARCHAR(50) NOT NULL COMMENT 'Fineract source column code_name',
    -- column_id: b4d48d6f-de7c-41b0-b98f-67822e01eac5
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
