-- DWD generated from m_guarantor_funding_details
DROP TABLE IF EXISTS retail_banking_dm.dwd_guarantee_commitment_snapshot;
-- table_id: 0104a26b-5efe-4a50-b8c7-c55180c58bd0
CREATE TABLE IF NOT EXISTS retail_banking_dm.dwd_guarantee_commitment_snapshot (
    -- column_id: a6326fec-182d-48a4-a5f0-573189153dc1
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: f45c64a2-d6e9-4f27-a25a-bd13b1294e05
    `guarantor_id` BIGINT NOT NULL COMMENT 'Fineract source column guarantor_id',
    -- column_id: 3fdd57c6-7e20-46b9-b8e7-a133bba134d7
    `account_associations_id` BIGINT NOT NULL COMMENT 'Fineract source column account_associations_id',
    -- column_id: 9253bd54-a665-49ba-9ade-3b61e4263016
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 5b350e6e-2cf3-431c-b59f-12d604bb1fe9
    `amount_released_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_released_derived',
    -- column_id: cb2351a3-a45e-4686-ab3d-b0a082ee38af
    `amount_remaining_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_remaining_derived',
    -- column_id: 81c2d67a-8e41-46c5-80a2-58340fc08281
    `amount_transfered_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_transfered_derived',
    -- column_id: 2407ab12-8257-4090-80f3-71fe308ce948
    `status_enum` SMALLINT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: 123db211-1793-4146-9451-bde7eb863769
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
