-- ODS mirror of Apache Fineract m_appuser (平台运营与安全)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_appuser;
-- table_id: 507f67a1-455d-4957-8c52-e1160e2eccb7
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_appuser (
    -- column_id: dfd1fca4-8785-4899-806f-76076e3998f7
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 50692ea0-8c60-4fee-96fc-4026e5b9013d
    `is_deleted` BOOLEAN NOT NULL COMMENT 'Fineract source column is_deleted',
    -- column_id: 11a8baec-d4ba-40fc-a6eb-09eb99c8c7f9
    `office_id` BIGINT NULL COMMENT 'Fineract source column office_id',
    -- column_id: 2bf22a2c-6899-4bab-bff1-f5a8d659f8e2
    `staff_id` BIGINT NULL COMMENT 'Fineract source column staff_id',
    -- column_id: f7746079-efe8-490d-b4e7-f7064f67afa8
    `username` VARCHAR(100) NOT NULL COMMENT 'Fineract source column username',
    -- column_id: 9c7c0063-fcb6-4543-86c0-0f4e3ff12db4
    `firstname` VARCHAR(100) NOT NULL COMMENT 'Fineract source column firstname',
    -- column_id: d101f468-9492-4e35-8222-af01fd6086da
    `lastname` VARCHAR(100) NOT NULL COMMENT 'Fineract source column lastname',
    -- column_id: b09e68d2-4577-4fce-b260-6efcec3ff1dd
    `password` VARCHAR(255) NOT NULL COMMENT 'Fineract source column password',
    -- column_id: cb414588-25a2-43cd-8ca4-3c132f67fe36
    `email` VARCHAR(100) NOT NULL COMMENT 'Fineract source column email',
    -- column_id: a23ff271-3420-4d74-ab20-69d9b77ceb41
    `firsttime_login_remaining` BOOLEAN NOT NULL COMMENT 'Fineract source column firsttime_login_remaining',
    -- column_id: ceb748a0-54d5-4f69-af1f-2853d45fedf3
    `nonexpired` BOOLEAN NOT NULL COMMENT 'Fineract source column nonexpired',
    -- column_id: c65b4214-0ee9-4477-9211-13db03afdd8a
    `nonlocked` BOOLEAN NOT NULL COMMENT 'Fineract source column nonlocked',
    -- column_id: a0e230a1-0b49-4db8-8e11-235ff7a37e8b
    `nonexpired_credentials` BOOLEAN NOT NULL COMMENT 'Fineract source column nonexpired_credentials',
    -- column_id: fe234208-5c17-40dd-a12f-07a2dc1b81e5
    `enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column enabled',
    -- column_id: 8c935c8f-66e0-41b0-aec7-5b29e9c56df2
    `last_time_password_updated` DATE NOT NULL COMMENT 'Fineract source column last_time_password_updated',
    -- column_id: 94b0fac1-8746-4efd-8b98-4839e16b69c0
    `password_never_expires` BOOLEAN NOT NULL COMMENT 'define if the password, should be check for validity period or not',
    -- column_id: 2f28e1d5-9df0-4a59-a295-a7438cbaf5b6
    `cannot_change_password` BOOLEAN NULL COMMENT 'Fineract source column cannot_change_password',
    -- column_id: 56db85f9-e006-422f-bb38-76e4ac7053fb
    `password_reset_required` BOOLEAN NOT NULL COMMENT 'Fineract source column password_reset_required',
    -- column_id: 3d240cef-64ac-458c-a0d6-8f0ce353bd0b
    `failed_login_attempts` INT NOT NULL COMMENT 'Fineract source column failed_login_attempts',
    -- column_id: 239f2039-4da8-4750-bfeb-cdd67ddfff8a
    `is_login_retries_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column is_login_retries_enabled',
    -- column_id: 0a65cfcd-29f0-4cbc-acd1-1b7ab0e486e4
    `temporary_password` VARCHAR(255) NULL COMMENT 'Fineract source column temporary_password',
    -- column_id: 9de1d9b5-d235-4a32-981c-c261dfdc3036
    `temporary_password_expiry_time` DATETIME NULL COMMENT 'Fineract source column temporary_password_expiry_time',
    -- column_id: 96814859-98ed-4515-a335-bc7ea20350d4
    `is_password_reset_enabled` BOOLEAN NOT NULL COMMENT 'Fineract source column is_password_reset_enabled',
    -- column_id: d90f3fb8-c7e5-4842-b445-14f6dc7ace12
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
