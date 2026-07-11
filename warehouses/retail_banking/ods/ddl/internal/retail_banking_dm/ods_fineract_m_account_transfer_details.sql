-- ODS mirror of Apache Fineract m_account_transfer_details (支付结算)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_account_transfer_details;
-- table_id: 57671423-d01c-456a-89a7-285680734a24
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_account_transfer_details (
    -- column_id: af3463de-89be-44b5-9303-7f00e50404e9
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: cf7247f5-2ee6-4d0c-bf9c-c3d60be8a592
    `from_office_id` BIGINT NOT NULL COMMENT 'Fineract source column from_office_id',
    -- column_id: 1212f8a8-4034-4344-9943-a7729e9b8022
    `to_office_id` BIGINT NOT NULL COMMENT 'Fineract source column to_office_id',
    -- column_id: 40790e09-661d-422c-b4fa-c980db1d3670
    `from_client_id` BIGINT NULL COMMENT 'Fineract source column from_client_id',
    -- column_id: 9c9d4699-fb43-44b4-8482-f817fe8f7146
    `to_client_id` BIGINT NULL COMMENT 'Fineract source column to_client_id',
    -- column_id: cfd261af-04f4-4935-9224-d34f3451a823
    `from_savings_account_id` BIGINT NULL COMMENT 'Fineract source column from_savings_account_id',
    -- column_id: b124164e-dcad-476e-8443-0ea0d8fdb4db
    `to_savings_account_id` BIGINT NULL COMMENT 'Fineract source column to_savings_account_id',
    -- column_id: ba422d10-2987-4d4b-bf6d-6bf0e19a4540
    `from_loan_account_id` BIGINT NULL COMMENT 'Fineract source column from_loan_account_id',
    -- column_id: 0095947f-2d70-4c39-a7ab-4226d170cd8e
    `to_loan_account_id` BIGINT NULL COMMENT 'Fineract source column to_loan_account_id',
    -- column_id: 18efbbc0-3b7a-45ac-9e3b-955d1447e700
    `transfer_type` SMALLINT NULL COMMENT 'Fineract source column transfer_type',
    -- column_id: 742808a0-c0db-4b26-8fc0-f59e87ddad4d
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
