-- DIM generated from m_client
DROP TABLE IF EXISTS retail_banking_dm.dim_customer;
-- table_id: 53ba39df-d76f-400a-84db-38580d8594f1
CREATE TABLE IF NOT EXISTS retail_banking_dm.dim_customer (
    -- column_id: 6f0bba6a-bf80-4e23-9304-bd04aa76d55c
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 62d032a8-4269-45af-932f-71bcaf921eac
    `account_no` VARCHAR(64) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: f0ed6c26-9909-4298-9673-3cb44da8cc21
    `external_id` VARCHAR(64) NULL COMMENT 'Fineract source column external_id',
    -- column_id: b5af0cda-5ec5-4e67-8bd3-f61f98061475
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: e5a2a2ec-78ca-45b8-90d3-3e2beb29c799
    `sub_status` INT NULL COMMENT 'Fineract source column sub_status',
    -- column_id: 5cf820e6-2ae3-4240-abcb-73f34771c1cc
    `activation_date` DATE NULL COMMENT 'Fineract source column activation_date',
    -- column_id: 097e351c-3203-425e-b644-19280b92aafc
    `office_joining_date` DATE NULL COMMENT 'Fineract source column office_joining_date',
    -- column_id: 82e26b30-ec8c-41d2-be27-8e99f0edd306
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 9efce6d6-f2a7-4982-937c-83b3642254e3
    `transfer_to_office_id` BIGINT NULL COMMENT 'Fineract source column transfer_to_office_id',
    -- column_id: db8823f3-e2d6-4e1b-b1ec-0febef147780
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 72bd5014-fb6e-4170-b451-361050c620aa
    `firstname` VARCHAR(256) NULL COMMENT 'Fineract source column firstname',
    -- column_id: dbe059e8-c32a-4821-894a-d50d656a12b3
    `middlename` VARCHAR(256) NULL COMMENT 'Fineract source column middlename',
    -- column_id: 09bf8482-095b-4e25-a7f3-c8ca128fe94c
    `lastname` VARCHAR(256) NULL COMMENT 'Fineract source column lastname',
    -- column_id: 04c9762a-469b-4837-b5bc-889265c24ae4
    `fullname` VARCHAR(256) NULL COMMENT 'Fineract source column fullname',
    -- column_id: 5aa82338-fded-4b4e-ba3a-4a4fa7d0efab
    `display_name` VARCHAR(256) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: a920a947-8eaa-44be-8e89-0fa48f1f5cad
    `mobile_no` VARCHAR(64) NULL COMMENT 'Fineract source column mobile_no',
    -- column_id: 16e0da7d-9044-44dd-8671-c7ef145ea17f
    `is_staff` BOOLEAN NOT NULL COMMENT 'Fineract source column is_staff',
    -- column_id: 52f715bc-5517-4ef7-9559-4f7c5c92be13
    `gender_cv_id` INT NULL COMMENT 'Fineract source column gender_cv_id',
    -- column_id: 77dfd1ac-f8a0-43cd-b92d-60084d8dc74c
    `date_of_birth` VARCHAR(256) NULL COMMENT 'Fineract source column date_of_birth',
    -- column_id: da353b3c-81d7-420d-901b-08625bb8dd15
    `image_id` BIGINT NULL COMMENT 'Fineract source column image_id',
    -- column_id: 1c99caef-c982-4fb0-8bdc-7f4caab23d3d
    `closure_reason_cv_id` INT NULL COMMENT 'Fineract source column closure_reason_cv_id',
    -- column_id: 4f82f8aa-fb57-4b47-b895-316b652f630f
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: f15034e6-dc2a-4b4b-a1f1-25d5154fd369
    `updated_by` BIGINT NULL COMMENT 'Fineract source column updated_by',
    -- column_id: 9570ecac-8049-4aea-b2a6-2d717e69893e
    `updated_on` DATE NULL COMMENT 'Fineract source column updated_on',
    -- column_id: 957d0ff7-2264-4b93-af70-94d74eb09b1c
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 54f31ab0-7c6a-4df1-ba7d-42b98dec31e5
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: 57444c12-eedf-437f-9e06-adb63d9b990b
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 97771d8e-8d75-420a-8fa1-f9e2b9f3256f
    `default_savings_product` BIGINT NULL COMMENT 'Fineract source column default_savings_product',
    -- column_id: 3c7f8f74-213c-41fb-97e3-21641f18762a
    `default_savings_account` BIGINT NULL COMMENT 'Fineract source column default_savings_account',
    -- column_id: 53d67bd8-8dce-4fed-a5cf-9274e547c2b9
    `client_type_cv_id` INT NULL COMMENT 'Fineract source column client_type_cv_id',
    -- column_id: 297517f9-547b-4bc2-938e-2057938172d8
    `client_classification_cv_id` INT NULL COMMENT 'Fineract source column client_classification_cv_id',
    -- column_id: 37122914-b36c-4ba8-9885-123eea585d76
    `reject_reason_cv_id` INT NULL COMMENT 'Fineract source column reject_reason_cv_id',
    -- column_id: dadf710c-a3f5-49d3-bf43-53a3c481e85b
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: b506b049-d5de-42cf-af49-78d828c44b9b
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: 59ec5c0a-7f2c-4872-b830-2cb90775f94d
    `withdraw_reason_cv_id` INT NULL COMMENT 'Fineract source column withdraw_reason_cv_id',
    -- column_id: 01b7aab6-2e9d-4f01-bcab-b11e610b16f2
    `withdrawn_on_date` DATE NULL COMMENT 'Fineract source column withdrawn_on_date',
    -- column_id: 41351114-d6ce-498c-8c7d-6b2169c584f3
    `withdraw_on_userid` BIGINT NULL COMMENT 'Fineract source column withdraw_on_userid',
    -- column_id: 9999e7ce-58de-43a5-8987-2434079c89fd
    `reactivated_on_date` DATE NULL COMMENT 'Fineract source column reactivated_on_date',
    -- column_id: 8ca38756-0ccd-4dc1-8db7-487448969857
    `reactivated_on_userid` BIGINT NULL COMMENT 'Fineract source column reactivated_on_userid',
    -- column_id: 39622063-e9f6-4e21-8a9d-c05eb4a27424
    `legal_form_enum` INT NULL COMMENT 'Fineract source column legal_form_enum',
    -- column_id: 346afcbd-76a3-42a8-913a-75d48905dbcf
    `reopened_on_date` DATE NULL COMMENT 'Fineract source column reopened_on_date',
    -- column_id: 1fe9a7ab-8aab-473e-a4c4-300a8842d173
    `reopened_by_userid` BIGINT NULL COMMENT 'Fineract source column reopened_by_userid',
    -- column_id: b282d6b6-fba4-4a01-9abb-4af97fdb53de
    `email_address` VARCHAR(64) NULL COMMENT 'Fineract source column email_address',
    -- column_id: 75263a97-4340-4d17-b4c5-9cce44ff33af
    `proposed_transfer_date` DATE NULL COMMENT 'Fineract source column proposed_transfer_date',
    -- column_id: fdfcd5cf-9a4c-445b-8037-da0da1169931
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: d2f0480d-72ed-427f-9f46-f467c3b8cba1
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: e402dd9c-c679-48a7-9d11-e9bb24945432
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 598a017e-da28-41d7-9d40-e80dbad842d4
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 747353dc-f874-4191-8d3f-7ff18c2b2545
    `etl_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
