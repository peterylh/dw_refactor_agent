-- ODS mirror of Apache Fineract m_loan_charge (贷款与信贷)
DROP TABLE IF EXISTS retail_banking_dm.ods_fineract_m_loan_charge;
-- table_id: 4c5c09c0-353b-4eec-bf0a-81244f5fcf48
CREATE TABLE IF NOT EXISTS retail_banking_dm.ods_fineract_m_loan_charge (
    -- column_id: 841ce67c-2146-454e-ace6-6eb508f2b185
    `id` BIGINT NOT NULL COMMENT 'Fineract source column id',
    -- column_id: 4acbfb6e-a35a-4866-ba58-f3889beb6f6b
    `loan_id` BIGINT NOT NULL COMMENT 'Fineract source column loan_id',
    -- column_id: fffa5c8f-e8a0-4276-b16b-f0d7586b499e
    `charge_id` BIGINT NOT NULL COMMENT 'Fineract source column charge_id',
    -- column_id: 9edb943a-02e7-46d7-8251-b2fce7031b4b
    `is_penalty` BOOLEAN NOT NULL COMMENT 'Fineract source column is_penalty',
    -- column_id: 4c560b74-7b89-4d43-99bc-42ac32b3014d
    `charge_time_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_time_enum',
    -- column_id: d2053699-8152-46bd-abd9-8822c69f6a12
    `due_for_collection_as_of_date` DATE NULL COMMENT 'Fineract source column due_for_collection_as_of_date',
    -- column_id: 1d945405-5797-4d45-b784-301cbf0c2aed
    `charge_calculation_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_calculation_enum',
    -- column_id: d67aa253-ddd1-40c8-8d68-2a57f84e736f
    `charge_payment_mode_enum` SMALLINT NOT NULL COMMENT 'Fineract source column charge_payment_mode_enum',
    -- column_id: d5945d61-9039-43d8-ae75-2fb32e423baa
    `calculation_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_percentage',
    -- column_id: ce70b78a-8e75-458f-919c-22aa968e8c88
    `calculation_on_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column calculation_on_amount',
    -- column_id: 522c9052-3d63-4861-a241-89aa2303cfad
    `charge_amount_or_percentage` DECIMAL(19,6) NULL COMMENT 'Fineract source column charge_amount_or_percentage',
    -- column_id: 2337ba57-9986-43cb-8eb9-f188ddd9f6e4
    `amount` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount',
    -- column_id: 36a240f6-c907-4f11-83b5-2fa5f0b9b87b
    `amount_paid_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_paid_derived',
    -- column_id: 25fdca2f-4ebb-4281-99f2-28de47d63b2c
    `amount_waived_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_waived_derived',
    -- column_id: d3d7e37a-6a67-4b24-82b9-54dbe2466426
    `amount_writtenoff_derived` DECIMAL(19,6) NULL COMMENT 'Fineract source column amount_writtenoff_derived',
    -- column_id: a173efcf-3cd2-4965-a3a2-25d2f783c68c
    `amount_outstanding_derived` DECIMAL(19,6) NOT NULL COMMENT 'Fineract source column amount_outstanding_derived',
    -- column_id: 25179bec-9a81-40ce-90c9-536da373fa48
    `is_paid_derived` BOOLEAN NOT NULL COMMENT 'Fineract source column is_paid_derived',
    -- column_id: 8be2007b-c4dd-4d36-9f32-2da443423d61
    `waived` BOOLEAN NOT NULL COMMENT 'Fineract source column waived',
    -- column_id: 2384b725-2744-44a8-b5cb-339a19d8e7c8
    `min_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column min_cap',
    -- column_id: 9fd0ffa2-8f4d-4871-ad52-6f94067c6e31
    `max_cap` DECIMAL(19,6) NULL COMMENT 'Fineract source column max_cap',
    -- column_id: b91d4a9b-3f2d-4608-8047-5ab04da2dc1b
    `is_active` BOOLEAN NOT NULL COMMENT 'Fineract source column is_active',
    -- column_id: 142eee3f-cef9-4924-87af-13023896f642
    `external_id` VARCHAR(100) NULL COMMENT 'Fineract source column external_id',
    -- column_id: 97779de9-c362-420b-ab9a-fcdcf1ab6ddf
    `submitted_on_date` DATE NULL COMMENT 'Fineract source column submitted_on_date',
    -- column_id: 105c5f73-51cb-43bc-b186-12b9cf365e92
    `created_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column created_on_utc',
    -- column_id: 1f119e83-e2f0-4723-96b4-4c1f4591f6c4
    `last_modified_on_utc` DATETIME NOT NULL COMMENT 'Fineract source column last_modified_on_utc',
    -- column_id: 2f024af5-c6be-4823-8554-810b05bd1bb7
    `created_by` BIGINT NOT NULL COMMENT 'Fineract source column created_by',
    -- column_id: 3bdbb006-8d7c-4d7e-af14-5d9235317994
    `last_modified_by` BIGINT NOT NULL COMMENT 'Fineract source column last_modified_by',
    -- column_id: 27c02b96-9330-4232-b135-7b7b93c07549
    `tax_amount` DECIMAL(19,6) NULL COMMENT 'Fineract source column tax_amount',
    -- column_id: 382eb260-3b1b-48e3-87bb-5551496f219f
    `load_time` DATETIME NOT NULL COMMENT '数仓技术时间'
) ENGINE=OLAP
DUPLICATE KEY(`id`)
DISTRIBUTED BY HASH(`id`) BUCKETS 1
PROPERTIES ("replication_num" = "1");
