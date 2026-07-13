SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_charge
DELETE FROM retail_banking_dm.dwd_loan_charge
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_loan_charge
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_loan_charge (
    `id`,
    `loan_id`,
    `charge_id`,
    `is_penalty`,
    `charge_time_enum`,
    `due_for_collection_as_of_date`,
    `charge_calculation_enum`,
    `charge_payment_mode_enum`,
    `calculation_percentage`,
    `calculation_on_amount`,
    `charge_amount_or_percentage`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `min_cap`,
    `max_cap`,
    `is_active`,
    `external_id`,
    `submitted_on_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `created_by`,
    `last_modified_by`,
    `tax_amount`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`charge_id`,
    src.`is_penalty`,
    src.`charge_time_enum`,
    src.`due_for_collection_as_of_date`,
    src.`charge_calculation_enum`,
    src.`charge_payment_mode_enum`,
    src.`calculation_percentage`,
    src.`calculation_on_amount`,
    src.`charge_amount_or_percentage`,
    src.`amount`,
    src.`amount_paid_derived`,
    src.`amount_waived_derived`,
    src.`amount_writtenoff_derived`,
    src.`amount_outstanding_derived`,
    src.`is_paid_derived`,
    src.`waived`,
    src.`min_cap`,
    src.`max_cap`,
    src.`is_active`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`submitted_on_date`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`tax_amount`,
    DATE(src.`due_for_collection_as_of_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_charge AS src
WHERE DATE(src.`due_for_collection_as_of_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`due_for_collection_as_of_date`) IS NULL;
