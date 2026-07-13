-- DWD generated from m_client_address
DROP TABLE IF EXISTS retail_banking_dm.bridge_customer_address;
-- table_id: 17df5fe5-0653-4144-ba0b-88e4f78a17ae
CREATE TABLE IF NOT EXISTS retail_banking_dm.bridge_customer_address (
    -- column_id: cc122ca3-abae-4a65-a2d7-3f475e573bdb
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: e9d85b00-3693-420a-8bdb-1a403e3eca4d
    `client_id` BIGINT NOT NULL COMMENT 'Fineract source column client_id',
    -- column_id: 66923059-d386-405e-9c84-5bcf42ae9593
    `address_id` BIGINT NOT NULL COMMENT 'Fineract source column address_id',
    -- column_id: b28a4233-ddc1-40ff-b7da-dd86a92782e9
    `address_type_id` INT NOT NULL COMMENT 'Fineract source column address_type_id',
    -- column_id: 2473b5e4-6199-4d0f-bef4-4dbbc2df9dff
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 0900f241-05d7-4511-9406-a757e3d739b3
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
