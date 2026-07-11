SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_client_charge
TRUNCATE TABLE retail_banking_dm.dwd_client_charge;

INSERT INTO retail_banking_dm.dwd_client_charge (
    `id`,
    `client_id`,
    `charge_id`,
    `is_penalty`,
    `charge_time_enum`,
    `charge_due_date`,
    `charge_calculation_enum`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `is_active`,
    `inactivated_on_date`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`charge_id`,
    src.`is_penalty`,
    src.`charge_time_enum`,
    src.`charge_due_date`,
    src.`charge_calculation_enum`,
    src.`amount`,
    src.`amount_paid_derived`,
    src.`amount_waived_derived`,
    src.`amount_writtenoff_derived`,
    src.`amount_outstanding_derived`,
    src.`is_paid_derived`,
    src.`waived`,
    src.`is_active`,
    src.`inactivated_on_date`,
    DATE(src.`charge_due_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_charge AS src;
