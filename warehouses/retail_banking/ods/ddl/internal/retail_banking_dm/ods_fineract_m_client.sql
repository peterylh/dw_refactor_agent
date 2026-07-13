-- ODS mirror of Apache Fineract m_client (客户与参与方)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_client;
-- table_id: 084ca3d0-84dd-4c80-b02b-d396f6276d67
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_client (
    -- column_id: b49881bf-acf8-46fa-ad62-48f846565a60
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 26a6f38e-c7a7-4c21-8130-57ca137091ed
    `account_no` VARCHAR(20) NOT NULL COMMENT 'Fineract source column account_no',
    -- column_id: 686cf3fe-4178-4e4c-98ae-66158a9a3825
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 190c3f21-866b-4c45-8030-d0076fef8ad7
    `status_enum` INT NOT NULL COMMENT 'Fineract source column status_enum',
    -- column_id: acfd9752-3f03-4b4a-a62a-0e6075a37b63
    `sub_status` INT NULL COMMENT 'Fineract source column sub_status',
    -- column_id: b54cbfef-74b0-430c-ac57-e985ac151781
    `activation_date` DATE NULL COMMENT 'Fineract source column activation_date',
    -- column_id: 494e70c0-5abe-4af3-bbc4-92cfa716dd95
    `office_joining_date` DATE NULL COMMENT 'Fineract source column office_joining_date',
    -- column_id: 4a770889-a1e9-4cee-bba8-21a7eca7975e
    `office_id` BIGINT NOT NULL COMMENT 'Fineract source column office_id',
    -- column_id: ea5231d5-1670-47ba-9278-2277951066be
    `transfer_to_office_id` BIGINT NULL COMMENT 'Fineract source column transfer_to_office_id',
    -- column_id: ebe982d3-54e9-46dc-9b64-56acfb74d434
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: 7a95c7ac-afd6-4d40-be64-564b13c71ac0
    `firstname` VARCHAR(50) NULL COMMENT 'Fineract source column firstname',
    -- column_id: 3f723b25-d3e6-4312-ae99-afa89a358da1
    `middlename` VARCHAR(50) NULL COMMENT 'Fineract source column middlename',
    -- column_id: 93ef8aa0-ef0e-4213-862c-1b22c2f3d001
    `lastname` VARCHAR(50) NULL COMMENT 'Fineract source column lastname',
    -- column_id: 9f04bc11-9733-43e8-a80f-29f2d6727fab
    `fullname` VARCHAR(160) NULL COMMENT 'Fineract source column fullname',
    -- column_id: c2792d3b-32d9-4cf7-890e-46fc349365b0
    `display_name` VARCHAR(160) NOT NULL COMMENT 'Fineract source column display_name',
    -- column_id: d54fe7a8-c7ba-444d-a1b0-65238882df0f
    `mobile_no` VARCHAR(50) NULL COMMENT 'Fineract source column mobile_no',
    -- column_id: eaf71b2a-08d6-4f98-82f3-2e341de0e69c
    `is_staff` BOOLEAN NOT NULL COMMENT 'Fineract source column is_staff',
    -- column_id: fa85811f-32aa-4b13-8d68-1bf078048165
    `gender_cv_id` INT NULL COMMENT 'Fineract source column gender_cv_id',
    -- column_id: dfc7c49d-9285-4093-986c-e8c3a79c531e
    `date_of_birth` DATE NULL COMMENT 'Fineract source column date_of_birth',
    -- column_id: 6832ae3d-3ea1-41cf-aa52-1242e6ce3c74
    `image_id` BIGINT NULL COMMENT 'Fineract source column image_id',
    -- column_id: 953cbb96-e75c-435c-b72d-c5184a8c17d1
    `closure_reason_cv_id` INT NULL COMMENT 'Fineract source column closure_reason_cv_id',
    -- column_id: 4fac2e4d-29bf-44e1-a064-8c1d798ddd5c
    `closedon_date` DATE NULL COMMENT 'Fineract source column closedon_date',
    -- column_id: bea7ada5-d49b-4af7-be3d-3268c7b855bd
    `updated_by` BIGINT NULL COMMENT 'Fineract source column updated_by',
    -- column_id: c83ff4bf-2c2b-4485-8f7a-6770da347493
    `updated_on` DATE NULL COMMENT 'Fineract source column updated_on',
    -- column_id: 5378c564-8ee2-47a9-bfea-5578ff1e40d6
    `submittedon_date` DATE NULL COMMENT 'Fineract source column submittedon_date',
    -- column_id: 1b8ceb45-4eb6-49a4-9beb-184a46ac401a
    `activatedon_userid` BIGINT NULL COMMENT 'Fineract source column activatedon_userid',
    -- column_id: cd9ac97a-ed77-47f2-be35-c62f68d4db75
    `closedon_userid` BIGINT NULL COMMENT 'Fineract source column closedon_userid',
    -- column_id: 2e1f75a7-0037-4231-9285-4e1b15e6df22
    `default_savings_product` BIGINT NULL COMMENT 'Fineract source column default_savings_product',
    -- column_id: 151007b5-282e-43a6-a19b-5d204c982fbf
    `default_savings_account` BIGINT NULL COMMENT 'Fineract source column default_savings_account',
    -- column_id: d506a493-fbc4-466a-a518-c6538d9f8d4c
    `client_type_cv_id` INT NULL COMMENT 'Fineract source column client_type_cv_id',
    -- column_id: 7b0c241d-fab0-4cec-908a-c6a1ec76ab01
    `client_classification_cv_id` INT NULL COMMENT 'Fineract source column client_classification_cv_id',
    -- column_id: b49e4d5b-ac1d-43ac-b047-ad1099b21b26
    `reject_reason_cv_id` INT NULL COMMENT 'Fineract source column reject_reason_cv_id',
    -- column_id: 184bcd9b-53a4-48f4-9d41-807f10287409
    `rejectedon_date` DATE NULL COMMENT 'Fineract source column rejectedon_date',
    -- column_id: 28d16d33-ce27-463d-890c-2a9f623ad0a2
    `rejectedon_userid` BIGINT NULL COMMENT 'Fineract source column rejectedon_userid',
    -- column_id: aa2623e6-2bd1-4fdc-96b5-d6cd9a098f2b
    `withdraw_reason_cv_id` INT NULL COMMENT 'Fineract source column withdraw_reason_cv_id',
    -- column_id: a2c89682-d7e3-4cce-b3c5-225543ff6711
    `withdrawn_on_date` DATE NULL COMMENT 'Fineract source column withdrawn_on_date',
    -- column_id: fd6918f5-cc74-4367-a31d-d82480e2dd3f
    `withdraw_on_userid` BIGINT NULL COMMENT 'Fineract source column withdraw_on_userid',
    -- column_id: 77059caf-fd80-42e8-baac-cc3077e8f475
    `reactivated_on_date` DATE NULL COMMENT 'Fineract source column reactivated_on_date',
    -- column_id: cef9594d-5087-4c0e-88a6-867cd271c784
    `reactivated_on_userid` BIGINT NULL COMMENT 'Fineract source column reactivated_on_userid',
    -- column_id: 711b28f2-8dd1-4d23-8096-eb150df5bc54
    `legal_form_enum` INT NULL COMMENT 'Fineract source column legal_form_enum',
    -- column_id: 760fad97-9c86-413a-9221-e92b480ffdcf
    `reopened_on_date` DATE NULL COMMENT 'Fineract source column reopened_on_date',
    -- column_id: 5a7df2b3-9963-406d-bc16-792a1b9e3c59
    `reopened_by_userid` BIGINT NULL COMMENT 'Fineract source column reopened_by_userid',
    -- column_id: b29bfe95-79d0-48e5-943b-e3b2980e8af6
    `email_address` VARCHAR(150) NULL COMMENT 'Fineract source column email_address',
    -- column_id: f8161c5c-1c61-47e9-8ea4-347ac262cbee
    `proposed_transfer_date` DATE NULL COMMENT 'Fineract source column proposed_transfer_date',
    -- column_id: 351806bb-cc13-4ddb-9825-6ff457f73819
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: c6b0a3e6-ff5f-4072-991b-9b53af63b95a
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 83c3b70b-62a1-418c-a6a6-f51582727a90
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: d25f1cb6-7190-4d12-ba02-67281f5bda5e
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 8b093857-cff3-43f1-a9eb-a4ffb6bb543b
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
